import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

from backend.app.api.routers import admin, auth, chat, documents, health
from backend.app.core.config import get_settings
from backend.app.db.session import engine

log = structlog.get_logger()
REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
REQUEST_SECONDS = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "path"]
)
settings = get_settings()
app = FastAPI(title="Enterprise RAG Knowledge Assistant", version="0.1.0")
provider = TracerProvider(resource=Resource.create({"service.name": "atlas-rag-api"}))
if settings.otel_exporter_otlp_endpoint:
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
    )
trace.set_tracer_provider(provider)
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
HTTPXClientInstrumentor().instrument()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("request_failed", request_id=request_id, path=request.url.path)
        response = JSONResponse(
            {"detail": "Internal server error", "request_id": request_id}, status_code=500
        )
    elapsed_ms = (time.perf_counter() - started) * 1000
    REQUESTS.labels(request.method, request.url.path, str(response.status_code)).inc()
    REQUEST_SECONDS.labels(request.method, request.url.path).observe(elapsed_ms / 1000)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    log.info(
        "request_complete",
        request_id=request_id,
        path=request.url.path,
        status=response.status_code,
        elapsed_ms=round(elapsed_ms, 2),
    )
    return response


app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
