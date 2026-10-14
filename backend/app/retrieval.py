from dataclasses import dataclass
from collections.abc import Sequence

from backend.app.config import Settings
from backend.app.contracts import EmbeddingProvider, GenerationProvider, RetrievedChunk, VectorStore
from backend.app.repository import get_or_create_learner, ready_chunks_by_ids


@dataclass(frozen=True)
class AnswerResult:
    text: str
    references: tuple[str, ...] = ()
    supported: bool = False

    def format_for_whatsapp(self) -> str:
        if not self.supported:
            return self.text
        refs = ", ".join(self.references)
        return f"{self.text}\n\nSources: {refs}"


def _bounded_context(chunks: Sequence[RetrievedChunk], max_chars: int) -> tuple[str, list[RetrievedChunk]]:
    sections: list[str] = []
    used: list[RetrievedChunk] = []
    remaining = max_chars
    for chunk in chunks:
        header = f"[Source {chunk.chunk_id}; material {chunk.material_id}; page {chunk.page_number}]\n"
        allowance = remaining - len(header)
        if allowance <= 0:
            break
        text = chunk.text[:allowance].strip()
        if not text:
            continue
        sections.append(header + text)
        used.append(chunk)
        remaining -= len(header) + len(text) + 2
        if remaining <= 0:
            break
    return "\n\n".join(sections), used


def answer_question(
    settings: Settings,
    sender: str,
    question: str,
    embeddings_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
    vector_store: VectorStore,
    top_k: int = 4,
) -> AnswerResult:
    learner_id = get_or_create_learner(settings, sender)
    query_vectors = embeddings_provider.embed_texts([question])
    if len(query_vectors) != 1:
        raise RuntimeError("Embedding provider returned an unexpected number of vectors.")
    candidates = vector_store.search(query_vectors[0], learner_id=learner_id, top_k=top_k)
    if not candidates:
        return AnswerResult("I don't have uploaded material that supports an answer yet.")

    stored = ready_chunks_by_ids(settings, learner_id, [chunk.chunk_id for chunk in candidates])
    stored_by_id = {str(row["chunk_id"]): row for row in stored}
    verified: list[RetrievedChunk] = []
    for candidate in candidates:
        row = stored_by_id.get(candidate.chunk_id)
        if not row:
            continue
        # Use SQLite's learner-owned source text as authoritative; Chroma carries the indexed copy.
        verified.append(
            RetrievedChunk(
                chunk_id=str(row["chunk_id"]),
                material_id=str(row["material_id"]),
                learner_id=str(row["learner_id"]),
                source_type=str(row["source_type"]),
                page_number=int(row["page_number"]),
                text=str(row["text"]),
                distance=candidate.distance,
            )
        )
    if not verified:
        return AnswerResult("I couldn't find ready study material that supports an answer.")

    context, used = _bounded_context(verified, settings.max_context_chars)
    if not used:
        return AnswerResult("I couldn't find ready study material that supports an answer.")
    answer = generation_provider.answer(question, context).strip()
    if not answer or answer.casefold() == "not_supported":
        return AnswerResult("I couldn't find support for that in your uploaded materials.")

    references = tuple(f"{chunk.chunk_id} (p. {chunk.page_number})" for chunk in used)
    return AnswerResult(answer, references, supported=True)
