from dataclasses import dataclass
import uuid

from backend.app.config import Settings
from backend.app.contracts import EmbeddingProvider, GenerationProvider, VectorStore
from backend.app.pdf import extract_pdf_pages, make_chunks
from backend.app.repository import (
    begin_material,
    get_material_summary,
    get_or_create_learner,
    mark_material_failed,
    mark_material_ready,
)


@dataclass(frozen=True)
class IngestionResult:
    material_id: str
    learner_id: str
    page_count: int
    chunk_count: int
    summary: str


def ingest_pdf(
    settings: Settings,
    sender: str,
    filename: str,
    data: bytes,
    message_sid: str,
    embeddings_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
    vector_store: VectorStore,
) -> IngestionResult:
    pages = extract_pdf_pages(data, settings.max_pdf_bytes, settings.max_pdf_pages)
    learner_id = get_or_create_learner(settings, sender)
    material_id = uuid.uuid5(uuid.NAMESPACE_URL, f"studychat:{sender}:{message_sid}").hex
    chunks = make_chunks(pages, material_id, learner_id)
    if not chunks:
        raise ValueError("No readable PDF text was found.")

    should_process = begin_material(settings, material_id, learner_id, filename, chunks)
    if not should_process:
        summary = get_material_summary(settings, material_id)
        if summary is None:
            raise RuntimeError("This upload is already being processed.")
        return IngestionResult(material_id, learner_id, len(pages), len(chunks), summary)

    try:
        vectors: list[list[float]] = []
        for offset in range(0, len(chunks), 64):
            vectors.extend(embeddings_provider.embed_texts([chunk.text for chunk in chunks[offset : offset + 64]]))
        if len(vectors) != len(chunks):
            raise RuntimeError("Embedding provider returned an unexpected number of vectors.")

        source_text = "\n\n".join(f"Page {page.page_number}\n{page.text}" for page in pages if page.text)
        summary = generation_provider.summarize(source_text, settings.max_context_chars)
        vector_store.upsert_chunks(chunks, vectors)
        mark_material_ready(settings, material_id, summary)
    except Exception as exc:
        mark_material_failed(settings, material_id, str(exc) or exc.__class__.__name__)
        raise

    return IngestionResult(material_id, learner_id, len(pages), len(chunks), summary)


def ingest_text(
    settings: Settings, sender: str, filename: str, source_type: str,
    source_text: str, message_sid: str,
    embeddings_provider: EmbeddingProvider, generation_provider: GenerationProvider,
    vector_store: VectorStore,
) -> IngestionResult:
    """Index one page of extracted photo/transcript text using the same persistent pipeline."""
    from backend.app.pdf import PageText, make_chunks

    if not source_text.strip():
        raise ValueError("No readable text was extracted from this upload.")
    learner_id = get_or_create_learner(settings, sender)
    material_id = uuid.uuid5(uuid.NAMESPACE_URL, f"studychat:{sender}:{message_sid}").hex
    chunks = make_chunks([PageText(1, source_text)], material_id, learner_id)
    chunks = [type(c)(c.chunk_id, c.material_id, c.learner_id, source_type, c.page_number, c.text) for c in chunks]
    if not begin_material(settings, material_id, learner_id, filename, chunks, source_type):
        summary = get_material_summary(settings, material_id)
        if summary is None:
            raise RuntimeError("This upload is already being processed.")
        return IngestionResult(material_id, learner_id, 1, len(chunks), summary)
    try:
        vectors = embeddings_provider.embed_texts([chunk.text for chunk in chunks])
        if len(vectors) != len(chunks):
            raise RuntimeError("Embedding provider returned an unexpected number of vectors.")
        summary = generation_provider.summarize(source_text, settings.max_context_chars)
        vector_store.upsert_chunks(chunks, vectors)
        mark_material_ready(settings, material_id, summary)
    except Exception as exc:
        mark_material_failed(settings, material_id, str(exc) or exc.__class__.__name__)
        raise
    return IngestionResult(material_id, learner_id, 1, len(chunks), summary)
