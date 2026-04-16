from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.endpoints import auth
from app.api.endpoints.document import router as document_router
from app.api.endpoints.knowledgebase import router as kb_router
from app.api.endpoints.chat import router as chat_router
from app.api.endpoints.feedback import router as feedback_router
from app.api.endpoints.eval import router as eval_router
from app.db import Base, engine

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Configure OpenTelemetry tracing with Console exporter BEFORE instrumentors
_tracer_provider = TracerProvider()
_tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(_tracer_provider)

from app.core.logging import setup_logging
from app.core.rate_limit import limiter, RateLimitExceeded, _rate_limit_exceeded_handler

setup_logging()


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
    
    # Instrument SQLAlchemy
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    yield
    await engine.dispose()


app = FastAPI(
    title="RAG Backend",
    description="Async document ingestion and retrieval API",
    version="0.2.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

FastAPIInstrumentor.instrument_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(document_router)
app.include_router(kb_router)
app.include_router(chat_router)
app.include_router(feedback_router)
app.include_router(eval_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
