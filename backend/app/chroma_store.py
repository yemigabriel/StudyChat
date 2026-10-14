from collections.abc import Sequence
from pathlib import Path

import chromadb

from backend.app.contracts import ChunkRecord, RetrievedChunk


class IncompatibleIndexError(RuntimeError):
    pass


class ChromaVectorStore:
    collection_name = "studychat_chunks"

    def __init__(self, path: Path, embedding_provider: str, embedding_model: str):
        self.client = chromadb.PersistentClient(path=str(path))
        self.embedding_provider = embedding_provider
        self.embedding_model = embedding_model

    def _collection(self, dimension: int | None):
        collections = self.client.list_collections()
        existing = any(
            collection == self.collection_name or getattr(collection, "name", None) == self.collection_name
            for collection in collections
        )
        if existing:
            collection = self.client.get_collection(self.collection_name, embedding_function=None)
            metadata = collection.metadata or {}
            if metadata.get("embedding_provider") != self.embedding_provider:
                raise IncompatibleIndexError("Chroma index embedding provider differs from configuration; re-index required.")
            if metadata.get("embedding_model") != self.embedding_model:
                raise IncompatibleIndexError("Chroma index embedding model differs from configuration; re-index required.")
            stored_dimension = metadata.get("embedding_dimension")
            if dimension is not None and stored_dimension != dimension:
                raise IncompatibleIndexError("Chroma index embedding dimension differs from query; re-index required.")
            return collection
        if dimension is None:
            return None
        return self.client.create_collection(
            name=self.collection_name,
            embedding_function=None,
            metadata={
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model,
                "embedding_dimension": dimension,
                "hnsw:space": "cosine",
            },
        )

    def upsert_chunks(self, chunks: Sequence[ChunkRecord], embeddings: Sequence[Sequence[float]]) -> None:
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk must have exactly one embedding")
        dimensions = {len(vector) for vector in embeddings}
        if len(dimensions) != 1 or not dimensions or 0 in dimensions:
            raise ValueError("Embedding vectors must all have the same non-zero dimension")
        dimension = dimensions.pop()
        collection = self._collection(dimension)
        collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=[list(vector) for vector in embeddings],
            metadatas=[
                {
                    "learner_id": chunk.learner_id,
                    "material_id": chunk.material_id,
                    "chunk_id": chunk.chunk_id,
                    "source_type": chunk.source_type,
                    "page_number": chunk.page_number,
                    "source_location": f"page:{chunk.page_number}",
                }
                for chunk in chunks
            ],
        )

    def search(
        self,
        query_embedding: Sequence[float],
        learner_id: str,
        material_id: str | None = None,
        top_k: int = 4,
    ) -> list[RetrievedChunk]:
        if top_k < 1:
            return []
        collection = self._collection(len(query_embedding))
        if collection is None or collection.count() == 0:
            return []
        learner_filter = {"learner_id": {"$eq": learner_id}}
        where = learner_filter if material_id is None else {
            "$and": [learner_filter, {"material_id": {"$eq": material_id}}]
        }
        result = collection.query(
            query_embeddings=[list(query_embedding)],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            RetrievedChunk(
                chunk_id=str(metadata["chunk_id"]),
                material_id=str(metadata["material_id"]),
                learner_id=str(metadata["learner_id"]),
                source_type=str(metadata["source_type"]),
                page_number=int(metadata["page_number"]),
                text=str(document),
                distance=float(distance),
            )
            for _chunk_id, document, metadata, distance in zip(ids, docs, metadatas, distances)
        ]
