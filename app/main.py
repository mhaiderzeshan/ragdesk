from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.endpoints import auth
from app.api.endpoints.document import router as document_router
from app.db import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Creates all DB tables if they don't exist yet.

    In production you'd use Alembic migrations instead of create_all.
    For now, this keeps it simple.
    """
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="RAG Backend",
    description="Async document ingestion and retrieval API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(document_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
