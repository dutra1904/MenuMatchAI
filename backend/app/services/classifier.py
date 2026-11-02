"""Classificação multirrótulo de tags alimentares.

O texto do prato vira TF-IDF (unigramas e bigramas). Um
`MultiOutputClassifier` de regressão logística prediz, ao mesmo tempo:

vegano, vegetariano, sem-lactose, sem-gluten, low-carb, proteico.

O treino usa só frases sintéticas. Alérgeno e dieta do cardápio continuam
curados: o modelo sugere tag, não substitui a trava de segurança da busca.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline

from app.config import BACKEND
from app.embeddings import fold

LABELS: tuple[str, ...] = (
    "vegano",
    "vegetariano",
    "sem-lactose",
    "sem-gluten",
    "low-carb",
    "proteico",
)
THRESHOLD = 0.55
DATA_PATH = BACKEND / "app" / "data" / "tag_train.json"


def _matrix(samples: list[dict]) -> tuple[list[str], np.ndarray]:
    texts = [item["text"] for item in samples]
    labels = np.array(
        [[1 if label in item["tags"] else 0 for label in LABELS] for item in samples],
        dtype=np.int8,
    )
    return texts, labels


def _pipeline() -> Pipeline:
    # O vetorizador cabe no pipeline para o vocabulário viajar com o modelo.
    classifier = MultiOutputClassifier(
        LogisticRegression(max_iter=800, class_weight="balanced", C=4.0),
    )
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=1,
                    preprocessor=fold,
                    sublinear_tf=True,
                ),
            ),
            ("clf", classifier),
        ]
    )


def load_samples() -> list[dict]:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    missing = [label for label in LABELS if not any(label in item["tags"] for item in payload)]
    if missing:
        raise ValueError(f"O treino não cobre as tags: {', '.join(missing)}")
    absent = [label for label in LABELS if all(label in item["tags"] for item in payload)]
    if absent:
        raise ValueError(f"O treino não tem exemplo negativo para: {', '.join(absent)}")
    return payload


@lru_cache(maxsize=1)
def get_classifier() -> Pipeline:
    samples = load_samples()
    texts, labels = _matrix(samples)
    model = _pipeline()
    model.fit(texts, labels)
    return model


def warm() -> None:
    get_classifier()


def predict_scores(text: str) -> dict[str, float]:
    model = get_classifier()
    probabilities = model.predict_proba([text])
    estimators = model.named_steps["clf"].estimators_
    scores: dict[str, float] = {}
    for label, proba, estimator in zip(LABELS, probabilities, estimators, strict=True):
        classes = list(estimator.classes_)
        positive = classes.index(1) if 1 in classes else None
        scores[label] = float(proba[0, positive]) if positive is not None else 0.0
    return scores


def predict_tags(text: str, threshold: float = THRESHOLD) -> list[str]:
    scores = predict_scores(text)
    return [label for label, score in scores.items() if score >= threshold]


def evaluate(cases: list[dict], threshold: float = THRESHOLD) -> dict[str, float]:
    """Precisão e recall macro nas tags, em um conjunto que não entra no treino."""
    true_positive = {label: 0 for label in LABELS}
    predicted_positive = {label: 0 for label in LABELS}
    actual_positive = {label: 0 for label in LABELS}
    for case in cases:
        predicted = set(predict_tags(case["text"], threshold))
        actual = set(case["tags"])
        for label in LABELS:
            if label in predicted:
                predicted_positive[label] += 1
            if label in actual:
                actual_positive[label] += 1
            if label in predicted and label in actual:
                true_positive[label] += 1
    precisions = []
    recalls = []
    for label in LABELS:
        precision = true_positive[label] / predicted_positive[label] if predicted_positive[label] else 1.0
        recall = true_positive[label] / actual_positive[label] if actual_positive[label] else 1.0
        precisions.append(precision)
        recalls.append(recall)
    return {
        "precision": float(np.mean(precisions)),
        "recall": float(np.mean(recalls)),
        "cases": float(len(cases)),
    }
