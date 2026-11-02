-- Alvo de produção do MenuMatch AI.
-- A API persiste o catálogo com SQLAlchemy (SQLite por padrão, ou PostgreSQL
-- via DATABASE_URL). Os embeddings ativos são MiniLM 384d, gravados em FAISS
-- no processo da API. Este script é a mesma busca por cosseno dentro do banco.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE restaurants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cuisine TEXT NOT NULL,
    rating DOUBLE PRECISION NOT NULL,
    zones JSONB NOT NULL
);

CREATE TABLE dishes (
    id TEXT PRIMARY KEY,
    restaurant_id TEXT NOT NULL REFERENCES restaurants (id),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    ingredients JSONB NOT NULL,
    allergens JSONB NOT NULL,
    tags JSONB NOT NULL,
    category TEXT NOT NULL,
    kind TEXT NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    prep_minutes INTEGER NOT NULL,
    embedding VECTOR(384)
);

CREATE INDEX dishes_embedding_idx
    ON dishes USING hnsw (embedding vector_cosine_ops);

CREATE TABLE orders (
    id TEXT PRIMARY KEY,
    restaurant_id TEXT NOT NULL,
    restaurant_name TEXT NOT NULL,
    zone TEXT NOT NULL,
    subtotal NUMERIC(10, 2) NOT NULL,
    delivery_fee NUMERIC(10, 2) NOT NULL,
    total NUMERIC(10, 2) NOT NULL,
    prep_minutes INTEGER NOT NULL,
    dietary_notes JSONB NOT NULL,
    customer_query TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders (id),
    dish_id TEXT NOT NULL,
    name TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL
);
