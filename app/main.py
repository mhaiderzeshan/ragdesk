from app.core.logging import setup_logging
setup_logging()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.document import router as document_router
from app.api.endpoints.knowledgebase import router as kb_router
from app.api.endpoints.chat import router as chat_router
from app.api.endpoints.feedback import router as feedback_router
from app.api.endpoints.eval import router as eval_router
from app.core.rate_limit import limiter, RateLimitExceeded, _rate_limit_exceeded_handler
from app.core.config import settings
from app.db import engine

# OTel setup 
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

logger = logging.getLogger(__name__)

def _configure_tracing() -> None:
    """
    Wires up the global tracer provider once at import time.
    Exporter type is driven by env var so dev vs prod differ
    without any code changes.
    """
    if settings.OTEL_EXPORTER == "otlp":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=settings.OTEL_ENDPOINT)
    else:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        exporter = ConsoleSpanExporter()

    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    logger.info("OTel tracing configured (exporter=%s)", settings.OTEL_EXPORTER)

# Singletons — called once at module level, never inside lifespan
_configure_tracing()
SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Starting up...")

    # Verify DB is reachable before accepting traffic
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("DB connection verified.")
    except OperationalError as e:
        logger.critical("DB unreachable on startup: %s", e, exc_info=True)
        raise  # Crash intentionally — don't serve with no DB

    # Ensure pgvector extension exists
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector extension ready.")
    except Exception as e:
        logger.critical("Failed to create pgvector extension: %s", e, exc_info=True)
        raise


    logger.info("Startup complete.")
    yield

    # --- Shutdown ---
    logger.info("Shutting down — disposing connection pool...")
    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="RAGDesk API",
    description="Async document ingestion and retrieval API",
    version="0.2.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

FastAPIInstrumentor.instrument_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

API_V1 = "/api/v1"
app.include_router(auth_router,     prefix=API_V1)
app.include_router(document_router, prefix=API_V1)
app.include_router(kb_router,       prefix=API_V1)
app.include_router(chat_router,     prefix=API_V1)
app.include_router(feedback_router, prefix=API_V1)
app.include_router(eval_router,     prefix=API_V1)


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Real health check — probes actual dependencies.
    Returns 503 if anything is down so orchestrators
    (Docker, k8s) don't route traffic to a broken instance.
    """
    from fastapi import status
    from fastapi.responses import JSONResponse

    checks = {}

    # Probe DB
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        logger.error("Health check: DB probe failed: %s", e)
        checks["db"] = "unreachable"

    overall_ok = all(v == "ok" for v in checks.values())
    status_code = status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if overall_ok else "degraded", "checks": checks},
    )
