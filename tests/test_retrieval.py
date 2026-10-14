from backend.app.chroma_store import ChromaVectorStore, IncompatibleIndexError
from backend.app.config import Settings
from backend.app.database import connect
from backend.app.ingestion import ingest_pdf

from test_pdf_ingestion import FakeOpenAIProvider, make_settings, make_text_pdf


class AnswerProvider(FakeOpenAIProvider):
    def __init__(self):
        self.last_context = ""

    def answer(self, question, context):
        self.last_context = context
        if "precipitation" in question.lower():
            return "NOT_SUPPORTED"
        return "Evaporation changes liquid water into vapor."


def test_retrieval_is_learner_scoped_and_formats_backend_source_reference(tmp_path):
    settings = make_settings(tmp_path)
    embeddings = FakeOpenAIProvider()
    answers = AnswerProvider()
    vectors = ChromaVectorStore(settings.chroma_path, "openai", embeddings.model_name)
    first = ingest_pdf(
        settings,
        "whatsapp:+15550000001",
        "water.pdf",
        make_text_pdf("Evaporation changes liquid water into vapor."),
        "SM" + "1" * 32,
        embeddings,
        embeddings,
        vectors,
    )
    ingest_pdf(
        settings,
        "whatsapp:+15550000002",
        "other.pdf",
        make_text_pdf("A learner's private astronomy notes."),
        "SM" + "2" * 32,
        embeddings,
        embeddings,
        vectors,
    )

    from backend.app.retrieval import answer_question

    result = answer_question(
        settings,
        "whatsapp:+15550000001",
        "What happens during evaporation?",
        embeddings,
        answers,
        vectors,
    )

    assert result.supported is True
    assert first.material_id in result.format_for_whatsapp()
    assert "astronomy" not in answers.last_context
    assert result.references and "p. 1" in result.references[0]


def test_unsupported_question_and_nonready_material_have_no_citations(tmp_path):
    settings = make_settings(tmp_path)
    embeddings = FakeOpenAIProvider()
    answers = AnswerProvider()
    vectors = ChromaVectorStore(settings.chroma_path, "openai", embeddings.model_name)
    material = ingest_pdf(
        settings,
        "whatsapp:+15550000003",
        "water.pdf",
        make_text_pdf("Evaporation changes liquid water into vapor."),
        "SM" + "3" * 32,
        embeddings,
        embeddings,
        vectors,
    )

    from backend.app.retrieval import answer_question

    unsupported = answer_question(
        settings,
        "whatsapp:+15550000003",
        "Explain precipitation.",
        embeddings,
        answers,
        vectors,
    )
    assert unsupported.supported is False
    assert unsupported.references == ()

    with connect(settings) as db:
        db.execute("UPDATE materials SET status='processing' WHERE material_id=?", (material.material_id,))
    unready = answer_question(
        settings,
        "whatsapp:+15550000003",
        "What is evaporation?",
        embeddings,
        answers,
        vectors,
    )
    assert unready.supported is False
    assert unready.references == ()


def test_chroma_refuses_an_incompatible_embedding_model(tmp_path):
    settings: Settings = make_settings(tmp_path)
    embeddings = FakeOpenAIProvider()
    vectors = ChromaVectorStore(settings.chroma_path, "openai", embeddings.model_name)
    ingest_pdf(
        settings,
        "whatsapp:+15550000004",
        "water.pdf",
        make_text_pdf("Evaporation changes liquid water into vapor."),
        "SM" + "4" * 32,
        embeddings,
        embeddings,
        vectors,
    )

    changed = ChromaVectorStore(settings.chroma_path, "openai", "another-embedding-model")
    try:
        changed.search([1.0, 0.0], "missing-learner")
    except IncompatibleIndexError as exc:
        assert "re-index" in str(exc)
    else:
        raise AssertionError("Expected model incompatibility to be rejected")
