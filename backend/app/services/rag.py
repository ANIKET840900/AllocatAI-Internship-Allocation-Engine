from __future__ import annotations

import re
from dataclasses import dataclass

_EMBEDDING_MODELS = {}

@dataclass
class Retrieval:
    text: str
    score: float
    metadata: dict


class Retriever:
    """FAISS/Sentence-Transformers when installed, deterministic lexical fallback otherwise."""

    def __init__(self, chunks: list[tuple[str, dict]]):
        self.chunks = chunks
        self._index = None
        self._model = None
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
            model_name = "all-MiniLM-L6-v2"
            if model_name not in _EMBEDDING_MODELS:
                _EMBEDDING_MODELS[model_name] = SentenceTransformer(model_name)
            self._model = _EMBEDDING_MODELS[model_name]
            vectors = self._model.encode([text for text, _ in chunks], normalize_embeddings=True)
            self._index = faiss.IndexFlatIP(vectors.shape[1])
            self._index.add(vectors)
        except ImportError:
            self._index = None
        except OSError:
            self._index = None

    def search(self, question: str, limit: int = 3) -> list[Retrieval]:
        if not self.chunks:
            return []
        if self._index is not None:
            scores, indices = self._index.search(self._model.encode([question], normalize_embeddings=True), min(limit, len(self.chunks)))
            return [Retrieval(self.chunks[i][0], float(score), self.chunks[i][1]) for score, i in zip(scores[0], indices[0]) if i >= 0]
        terms = set(re.findall(r"\w+", question.lower()))
        ranked = sorted(self.chunks, key=lambda item: len(terms & set(re.findall(r"\w+", item[0].lower()))), reverse=True)
        return [Retrieval(text, float(len(terms & set(re.findall(r"\w+", text.lower())))), meta) for text, meta in ranked[:limit] if terms & set(re.findall(r"\w+", text.lower()))]
