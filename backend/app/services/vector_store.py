"""Índice vetorial persistido.

Os vetores normalizados ficam em `vectors.npy`. Quando `faiss` está
instalado, o mesmo índice é gravado como `index.faiss` (IndexFlatIP,
produto interno = cosseno em vetores L2-normalizados).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    import faiss
except ImportError:  # pragma: no cover - depende da roda da plataforma
    faiss = None


@dataclass
class LoadedIndex:
    ids: list[str]
    vectors: np.ndarray
    signature: str
    backend: str


class VectorStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.ids: list[str] = []
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        self.backend = "faiss" if faiss is not None else "numpy"
        self._faiss = None

    def save(self, ids: list[str], vectors: np.ndarray, signature: str) -> None:
        matrix = np.ascontiguousarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or len(ids) != matrix.shape[0]:
            raise ValueError("A matriz de embeddings não bate com a lista de pratos.")
        self.directory.mkdir(parents=True, exist_ok=True)
        np.save(self.directory / "vectors.npy", matrix)
        meta = {
            "ids": ids,
            "signature": signature,
            "dimensions": int(matrix.shape[1]),
            "backend": self.backend,
            "metric": "cosine",
        }
        (self.directory / "index_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._faiss = None
        if faiss is not None and matrix.shape[0]:
            index = faiss.IndexFlatIP(matrix.shape[1])
            index.add(matrix)
            faiss.write_index(index, str(self.directory / "index.faiss"))
            self._faiss = index
        self.ids = list(ids)
        self.vectors = matrix

    def try_load(self, signature: str) -> LoadedIndex | None:
        meta_path = self.directory / "index_meta.json"
        matrix_path = self.directory / "vectors.npy"
        if not meta_path.exists() or not matrix_path.exists():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("signature") != signature:
            return None
        matrix = np.load(matrix_path)
        ids = list(meta["ids"])
        if len(ids) != matrix.shape[0]:
            return None
        self.ids = ids
        self.vectors = np.ascontiguousarray(matrix, dtype=np.float32)
        self._faiss = None
        faiss_path = self.directory / "index.faiss"
        if faiss is not None and faiss_path.exists():
            self._faiss = faiss.read_index(str(faiss_path))
            self.backend = "faiss"
        else:
            self.backend = "numpy"
        return LoadedIndex(ids=ids, vectors=self.vectors, signature=signature, backend=self.backend)

    def cosine(self, query: np.ndarray) -> np.ndarray:
        if self.vectors.size == 0:
            return np.zeros((0,), dtype=np.float32)
        vector = np.ascontiguousarray(query.reshape(1, -1), dtype=np.float32)
        if self._faiss is not None:
            index = self._faiss
            scores, positions = index.search(vector, self.vectors.shape[0])
            ordered = np.zeros((self.vectors.shape[0],), dtype=np.float32)
            for score, position in zip(scores[0], positions[0], strict=True):
                if position >= 0:
                    ordered[int(position)] = float(score)
            return ordered
        return (self.vectors @ vector.reshape(-1)).astype(np.float32)
