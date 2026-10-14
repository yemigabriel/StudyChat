from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    material_id: str
    learner_id: str
    source_type: str
    page_number: int
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    material_id: str
    learner_id: str
    source_type: str
    page_number: int
    text: str
    distance: float


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...


class GenerationProvider(Protocol):
    provider_name: str

    def summarize(self, source_text: str, max_context_chars: int) -> str: ...

    def answer(self, question: str, context: str) -> str: ...


class VectorStore(Protocol):
    def upsert_chunks(self, chunks: Sequence[ChunkRecord], embeddings: Sequence[Sequence[float]]) -> None: ...

    def search(
        self,
        query_embedding: Sequence[float],
        learner_id: str,
        material_id: str | None = None,
        top_k: int = 4,
    ) -> list[RetrievedChunk]: ...
