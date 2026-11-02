"""Embeddings densos com MiniLM multilíngue (ONNX via fastembed).

O checkpoint em inglês `all-MiniLM-L6-v2` existe no mesmo pacote, mas o
cardápio e as frases do cliente estão em português. O padrão é o
`paraphrase-multilingual-MiniLM-L12-v2` (384 dimensões). Os dois modelos
saem normalizados para a busca por cosseno.
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from app.config import BACKEND, settings

CACHE_DIR = BACKEND / ".cache" / "fastembed"
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingError(RuntimeError):
    pass


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise EmbeddingError(
            "Instale o pipeline de embeddings com: pip install -r requirements.txt"
        ) from exc
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return TextEmbedding(model_name=model_name, cache_dir=str(CACHE_DIR))


class SentenceEmbedder:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model or DEFAULT_MODEL
        self.dimensions = 384
        self._fitted = False

    def fit(self, texts: list[str]) -> None:
        if texts:
            matrix = self.embed(texts[:1])
            self.dimensions = int(matrix.shape[1])
        self._fitted = True

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimensions), dtype=np.float32)
        model = _load_model(self.model_name)
        rows = [np.asarray(vector, dtype=np.float32) for vector in model.embed(texts)]
        matrix = np.vstack(rows)
        self.dimensions = int(matrix.shape[1])
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.clip(norms, 1e-12, None)

    def transform(self, texts: list[str]) -> np.ndarray:
        return self.embed(texts)
