from io import BytesIO
import sqlite3

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from backend.app.chroma_store import ChromaVectorStore
from backend.app.config import Settings
from backend.app.ingestion import ingest_pdf
from backend.app.pdf import extract_pdf_pages
from backend.app.repository import material_status


def make_text_pdf(*page_texts):
    writer = PdfWriter()
    for text in page_texts:
        page = writer.add_blank_page(width=300, height=300)
        font = writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 50 250 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def make_settings(tmp_path):
    return Settings(
        _env_file=None,
        database_path=tmp_path / "studychat.sqlite3",
        chroma_path=tmp_path / "chroma",
        public_base_url="https://studychat.example",
        twilio_account_sid="AC" + "a" * 32,
        twilio_auth_token="twilio-test-secret",
        twilio_whatsapp_from="whatsapp:+15551234567",
        openai_api_key="sk-test-secret",
        max_pdf_pages=2,
    )


class FakeOpenAIProvider:
    provider_name = "openai"
    model_name = "fake-embedding-model"

    def embed_texts(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def summarize(self, source_text, max_context_chars):
        assert "Page 1" in source_text
        assert max_context_chars > 0
        return "• The water cycle includes evaporation and precipitation."

    def answer(self, question, context):
        raise AssertionError("answer() isn't part of ingestion")


def test_extract_pdf_text_preserves_page_numbers():
    data = make_text_pdf("Evaporation rises.", "Precipitation returns water.")

    pages = extract_pdf_pages(data, max_bytes=100_000, max_pages=10)

    assert [(page.page_number, page.text) for page in pages] == [
        (1, "Evaporation rises."),
        (2, "Precipitation returns water."),
    ]


def test_page_limit_and_scanned_pdf_limitation_are_explicit():
    with pytest.raises(ValueError, match="2-page"):
        extract_pdf_pages(make_text_pdf("one", "two", "three"), 100_000, 2)

    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    empty = BytesIO()
    writer.write(empty)
    with pytest.raises(ValueError, match="no selectable text"):
        extract_pdf_pages(empty.getvalue(), 100_000, 2)


def test_pdf_ingestion_persists_text_summary_and_explicit_vectors(tmp_path):
    settings = make_settings(tmp_path)
    provider = FakeOpenAIProvider()
    vectors = ChromaVectorStore(settings.chroma_path, "openai", provider.model_name)
    data = make_text_pdf("Evaporation turns liquid water into vapor.", "Condensation and precipitation complete the cycle.")

    result = ingest_pdf(
        settings,
        sender="whatsapp:+15557654321",
        filename="lesson.pdf",
        data=data,
        message_sid="SM" + "4" * 32,
        embeddings_provider=provider,
        generation_provider=provider,
        vector_store=vectors,
    )

    assert result.page_count == 2
    assert result.chunk_count == 2
    assert result.summary.startswith("• The water cycle")
    assert material_status(settings, result.material_id) == "ready"
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM source_chunks WHERE material_id=?", (result.material_id,)).fetchone()[0] == 2
        assert db.execute("SELECT summary FROM materials WHERE material_id=?", (result.material_id,)).fetchone()[0] == result.summary
    hits = vectors.search([1.0, 0.0], result.learner_id, material_id=result.material_id)
    assert len(hits) == 2
    assert {hit.page_number for hit in hits} == {1, 2}


def test_failed_index_does_not_mark_material_ready(tmp_path):
    settings = make_settings(tmp_path)
    provider = FakeOpenAIProvider()

    class BrokenVectorStore:
        def upsert_chunks(self, chunks, embeddings):
            raise RuntimeError("simulated index failure")

        def search(self, *args, **kwargs):
            return []

    data = make_text_pdf("Evaporation turns liquid water into vapor.")
    message_sid = "SM" + "5" * 32
    with pytest.raises(RuntimeError, match="simulated index failure"):
        ingest_pdf(
            settings,
            sender="whatsapp:+15557654321",
            filename="lesson.pdf",
            data=data,
            message_sid=message_sid,
            embeddings_provider=provider,
            generation_provider=provider,
            vector_store=BrokenVectorStore(),
        )

    material_id = __import__("uuid").uuid5(
        __import__("uuid").NAMESPACE_URL,
        f"studychat:whatsapp:+15557654321:{message_sid}",
    ).hex
    assert material_status(settings, material_id) == "failed"
