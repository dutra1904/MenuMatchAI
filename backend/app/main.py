import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.analytics import LatencyLog
from app.catalog import seed_orders_if_empty, sync_catalog
from app.config import settings
from app.db import SessionLocal, init_db
from app.errors import DishNotFound, RestaurantMismatch
from app.pricing import build_quote
from app.routes.api import router
from app.search import MenuIndex
from app.services.classifier import warm as warm_classifier

logger = logging.getLogger("menumatch")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as session:
        dishes = sync_catalog(session)
        seed_orders_if_empty(session, dishes, build_quote)
    warm_classifier()
    index = MenuIndex()
    index.build(dishes)
    app.state.index = index
    app.state.sessions = {}
    app.state.latency = LatencyLog()
    logger.info(
        "Índice pronto: %s pratos, %s dimensões (%s / %s)",
        index.meta["documents"],
        index.meta["dimensions"],
        index.meta["provider"],
        index.meta.get("vector_backend"),
    )
    yield


app = FastAPI(title="MenuMatch AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(DishNotFound)
async def dish_not_found(_request: Request, exc: DishNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"Prato não encontrado: {exc.dish_id}"})


@app.exception_handler(RestaurantMismatch)
async def restaurant_mismatch(_request: Request, _exc: RestaurantMismatch) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": "Os pratos precisam ser do mesmo restaurante."})


@app.exception_handler(ValueError)
async def invalid_order(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def invalid_body(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "Revise os campos enviados.", "errors": exc.errors()})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
