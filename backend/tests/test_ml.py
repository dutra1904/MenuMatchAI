import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.catalog import load_catalog
from app.services.classifier import evaluate, predict_tags
from app.services.sentence_embeddings import SentenceEmbedder
from app.services.vector_store import VectorStore
from app.search import MenuIndex

HELD_OUT = [
    {
        "text": "Salada verde com grão-de-bico, azeite e hortelã, sem laticínio e sem farinha",
        "tags": ["vegano", "vegetariano", "sem-lactose", "sem-gluten", "proteico"],
    },
    {
        "text": "Milk-shake cremoso de chocolate feito com leite integral e sorvete de creme",
        "tags": [],
    },
    {
        "text": "Filé de frango na brasa com salada, sem molho branco e sem pão",
        "tags": ["sem-lactose", "sem-gluten", "low-carb", "proteico"],
    },
    {
        "text": "Pizza de calabresa com bastante muçarela e massa de trigo",
        "tags": [],
    },
    {
        "text": "Tapioca doce só com banana e coco, sem leite condensado",
        "tags": ["vegano", "vegetariano", "sem-lactose", "sem-gluten"],
    },
]


def test_classifier_held_out_tags():
    metrics = evaluate(HELD_OUT)
    assert metrics["precision"] >= 0.75
    assert metrics["recall"] >= 0.75
    shake = set(predict_tags(HELD_OUT[1]["text"]))
    assert "vegano" not in shake
    assert "sem-lactose" not in shake
    salad = set(predict_tags(HELD_OUT[0]["text"]))
    assert {"vegano", "sem-lactose", "sem-gluten"} <= salad


def test_vector_store_persists_cosine_order(tmp_path):
    rng = np.random.default_rng(3)
    matrix = rng.normal(size=(4, 16)).astype(np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    store = VectorStore(tmp_path)
    store.save(["a", "b", "c", "d"], matrix, signature="test")
    assert (tmp_path / "vectors.npy").exists()
    assert (tmp_path / "index.faiss").exists()
    reloaded = VectorStore(tmp_path).try_load("test")
    assert reloaded is not None
    assert reloaded.ids == ["a", "b", "c", "d"]
    query = matrix[2]
    scores = store.cosine(query)
    assert int(np.argmax(scores)) == 2
    assert scores[2] > scores[0]


def test_minilm_puts_similar_dishes_closer():
    embedder = SentenceEmbedder()
    vectors = embedder.embed(
        [
            "poke de salmão com arroz e pepino",
            "tigela havaiana de salmão, arroz e gergelim",
            "milk-shake de chocolate com sorvete e biscoito",
        ]
    )
    assert vectors.shape == (3, 384)
    close = float(vectors[0] @ vectors[1])
    far = float(vectors[0] @ vectors[2])
    assert close > far
    assert close > 0.45


def test_api_exposes_embeddings_and_classifier():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        body = health.json()
        assert body["embedder"] == "minilm"
        assert body["dimensions"] == 384
        assert body["metric"] == "cosine"
        assert body["vector_backend"] == "faiss"
        assert "sem-lactose" in body["classifier_labels"]
        classified = client.post(
            "/api/classify",
            json={"text": "Tofu grelhado com brócolis, sem leite e sem pão"},
        )
        assert classified.status_code == 200
        tags = set(classified.json()["tags"])
        assert "vegano" in tags
        assert "sem-lactose" in tags
        menu = client.get("/api/menu", params={"q": "salada vegana leve", "diet": "vegan"})
        assert menu.status_code == 200
        assert menu.json()
        assert all("lactose" not in item["badges"] for item in menu.json())


def test_natural_language_search_uses_cosine_index():
    _restaurants, dishes = load_catalog()
    index = MenuIndex()
    index.build(dishes)
    assert index.meta["provider"] == "minilm"
    assert index.meta["dimensions"] == 384
    assert index.meta["metric"] == "cosine"
    assert index.meta["vector_backend"] == "faiss"
    results, relaxed = index.search(
        "almoço leve sem derivados de leite por menos de 40 reais",
        max_price=40,
        exclude_allergens=["lactose"],
    )
    assert relaxed is None
    assert results
    for dish in results:
        assert "lactose" not in dish.allergens
        assert dish.price <= 40
    query = index.embedder.embed(["almoço leve sem derivados de leite"])
    catalog = index.store.vectors
    scores = cosine_similarity(query, catalog)
    assert scores.shape[1] == len(dishes)
