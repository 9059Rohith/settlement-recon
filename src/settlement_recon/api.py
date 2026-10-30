"""Authenticated API. Health is public; business data and metrics require a token."""

import hmac
import logging
import os
import time
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from settlement_recon.domain import MAX_BYTES, DomainError, FileArchive, Reconciler

logger = logging.getLogger("settlement_recon")
bearer = HTTPBearer(auto_error=False)


def create_app(service: Reconciler, token: str, read_token: str = "") -> FastAPI:
    app = FastAPI(
        title="Settlement Recon",
        version="0.1.0",
        description=(
            "Synthetic cross-border payment reconciliation. Monetary strings use exact currency "
            "minor units. Upload JSON payments or CSV statements; "
            "inspect quarantine and replay results."
        ),
    )
    app.state.service = service
    registry = CollectorRegistry()
    requests = Counter(
        "settlement_recon_http_requests",
        "Completed HTTP requests",
        ["route", "status"],
        registry=registry,
    )
    duration = Histogram(
        "settlement_recon_http_seconds", "Request latency", ["route"], registry=registry
    )
    ingestion = Counter(
        "settlement_recon_batches", "Ingestion attempts", ["outcome"], registry=registry
    )

    def authenticate(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> str:
        if len(token.strip()) < 32:
            raise HTTPException(503, "Authentication is not configured")
        if credentials is None:
            raise HTTPException(
                401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"}
            )
        if hmac.compare_digest(credentials.credentials.encode(), token.encode()):
            return "writer"
        if len(read_token.strip()) >= 32 and hmac.compare_digest(
            credentials.credentials.encode(), read_token.encode()
        ):
            return "reader"
        raise HTTPException(401, "Invalid bearer token", headers={"WWW-Authenticate": "Bearer"})

    def writer(role: str = Depends(authenticate)):
        if role != "writer":
            raise HTTPException(403, "Writer role required")

    @app.middleware("http")
    async def observe(request: Request, call_next):
        started = time.perf_counter()
        request_id = str(uuid4())
        response = await call_next(request)
        route = getattr(request.scope.get("route"), "path", "unmatched")
        requests.labels(route, str(response.status_code)).inc()
        duration.labels(route).observe(time.perf_counter() - started)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        # No payloads, URLs, credentials or database strings in operational logs.
        logger.info(
            "request_completed route=%s status=%d request_id=%s",
            route,
            response.status_code,
            request_id,
        )
        return response

    @app.exception_handler(DomainError)
    async def domain_failure(_request: Request, error: DomainError):
        code = 404 if error.code == "not_found" else 413 if error.code == "size" else 422
        return JSONResponse({"detail": str(error), "code": error.code}, status_code=code)

    @app.exception_handler(SQLAlchemyError)
    async def database_failure(_request: Request, _error: SQLAlchemyError):
        logger.error("database_operation_failed")
        return JSONResponse({"detail": "Database operation unavailable; safe to retry input"}, 503)

    @app.exception_handler(OSError)
    async def archive_failure(_request: Request, _error: OSError):
        logger.error("archive_operation_failed")
        return JSONResponse({"detail": "Archive operation unavailable"}, 503)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def landing():
        return """<!doctype html><html lang='en'><meta charset='utf-8'>
        <meta name='viewport' content='width=device-width,initial-scale=1'>
        <title>Settlement Recon</title><body><main><h1>Settlement Recon</h1>
        <p>Auditable payment ingestion, exact reconciliation and controlled replay.</p>
        <p>Use the interactive API console to upload synthetic JSON and CSV, inspect
        batches, verify archived inputs and query reconciliation exceptions.</p>
        <p><a href='/docs'>Open API console</a> · <a href='/healthz'>Health</a> ·
        <a href='/readyz'>Readiness</a></p>
        <p>Business data requires an operator token. This system processes synthetic
        portfolio data and does not initiate or move money.</p></main></body></html>"""

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/readyz")
    def ready():
        try:
            with service.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            if hasattr(service.archive, "ready"):
                service.archive.ready()
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ready"}

    @app.post(
        "/v1/ingest/{kind}",
        dependencies=[Depends(writer)],
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "example": {
                                "payments": [
                                    {"payment_id": "p1", "currency": "USD", "amount": "10.00"}
                                ]
                            },
                        }
                    },
                    "text/csv": {"schema": {"type": "string"}},
                },
            },
        },
    )
    async def ingest(kind: str, request: Request, source: str):
        chunks = bytearray()
        async for chunk in request.stream():
            if len(chunks) + len(chunk) > MAX_BYTES:
                raise DomainError("Payload exceeds maximum size", "size")
            chunks.extend(chunk)
        result = await run_in_threadpool(service.ingest, kind, source, bytes(chunks))
        ingestion.labels("replayed" if result["replayed"] else result["status"]).inc()
        return result

    @app.get("/v1/reconciliation", dependencies=[Depends(authenticate)])
    def reconciliation():
        return service.reconcile()

    @app.get("/v1/batches", dependencies=[Depends(authenticate)])
    def list_batches():
        return service.batches()

    @app.get("/v1/batches/{batch_id}/verify", dependencies=[Depends(authenticate)])
    def verify(batch_id: str):
        return {"batch_id": batch_id, "intact": service.verify_archive(batch_id)}

    @app.get("/metrics", dependencies=[Depends(authenticate)], include_in_schema=False)
    def metrics():
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")

    return app


def from_environment() -> FastAPI:
    root = Path(os.environ.get("DATA_DIR", "data"))
    root.mkdir(parents=True, exist_ok=True)
    archive = FileArchive(root / "raw")
    bucket = os.environ.get("RAW_BUCKET")
    if bucket:
        from settlement_recon.s3 import S3Archive

        archive = S3Archive(bucket, os.environ.get("RAW_KMS_KEY_ARN"))
    database_url = os.environ.get("DATABASE_URL")
    if not database_url and os.environ.get("DB_HOST"):
        database_url = URL.create(
            "postgresql+psycopg",
            username=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            host=os.environ["DB_HOST"],
            port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ["DB_NAME"],
            query={"sslmode": os.environ.get("DB_SSLMODE", "prefer")},
        )
    service = Reconciler(database_url or f"sqlite:///{root / 'recon.db'}", archive)
    return create_app(service, os.environ.get("API_TOKEN", ""), os.environ.get("READ_TOKEN", ""))
