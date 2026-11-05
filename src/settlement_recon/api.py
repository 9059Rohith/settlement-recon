"""Authenticated API. Health is public; business data and metrics require a token."""

import base64
import hashlib
import hmac
import html
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import anyio
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from settlement_recon.domain import MAX_BYTES, DomainError, FileArchive, Reconciler
from settlement_recon.forensics_case import extract_case
from settlement_recon.forensics_http import install as install_forensics
from settlement_recon.forensics_models import ForensicsCase
from settlement_recon.schemas import ReconciliationExplanation

logger = logging.getLogger("settlement_recon")
bearer = HTTPBearer(auto_error=False)


def create_app(
    service: Reconciler,
    token: str,
    read_token: str = "",
    *,
    public_demo: bool = False,
    allowed_hosts: list[str] | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Settlement Recon",
        version="0.1.0",
        description=(
            "Operator-supplied payment reconciliation. Monetary strings use exact currency "
            "minor units. Upload JSON payments or CSV statements; "
            "inspect quarantine and replay results."
        ),
        swagger_ui_parameters={"validatorUrl": None},
    )
    app.state.service = service
    if allowed_hosts:
        hosts = list(allowed_hosts)
        deployment_host = os.getenv("VERCEL_URL", "")
        if os.getenv("VERCEL") == "1" and re.fullmatch(
            r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.vercel\.app", deployment_host
        ):
            hosts.append(deployment_host)
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)
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
        documentation_assets = {
            "/docs": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/",
            "/redoc": "https://cdn.jsdelivr.net/npm/redoc@2/bundles/",
        }
        if request.url.path in documentation_assets and response.headers.get(
            "content-type", ""
        ).startswith("text/html"):
            body = b"".join([chunk async for chunk in response.body_iterator])
            hashes = " ".join(
                "'sha256-" + base64.b64encode(hashlib.sha256(script).digest()).decode() + "'"
                for script in re.findall(rb"<script(?:\s[^>]*)?>(.*?)</script>", body, re.S)
                if script.strip()
            )
            response = Response(
                body,
                status_code=response.status_code,
                headers=dict(response.headers),
                background=response.background,
            )
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src "
                + hashes
                + " "
                + documentation_assets[request.url.path]
                + "; "
                "style-src 'unsafe-inline' " + documentation_assets[request.url.path] + "; "
                "connect-src 'self'; img-src 'self' data: https://fastapi.tiangolo.com; "
                "font-src data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            )
        route = getattr(request.scope.get("route"), "path", "unmatched")
        requests.labels(route, str(response.status_code)).inc()
        duration.labels(route).observe(time.perf_counter() - started)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path not in {"/docs", "/redoc"}:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self'; connect-src 'self'; "
                "style-src 'unsafe-inline'; font-src 'self'; img-src 'self'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            )
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
        code = {"not_found": 404, "size": 413, "integrity": 503}.get(error.code, 422)
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
        from settlement_recon.workspace import render

        return render()

    if not public_demo:

        @app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
        def workspace_entry():
            from settlement_recon.workspace import render

            return render()

    if public_demo:
        from settlement_recon.demo import summary

        @app.get("/demo/summary", tags=["Synthetic public demo"])
        def demo_summary():
            return summary(service)

        @app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
        def demo_dashboard():
            evidence = html.escape(json.dumps(summary(service), indent=2))
            return f"""<!doctype html><html lang="en"><meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Settlement Recon | Live evidence</title><style>
            body{{margin:0;background:#0d1525;color:#e5edf9;font:17px system-ui}}
            main{{max-width:900px;margin:6vh auto;padding:32px}}h1{{font-size:44px}}
            small,a{{color:#76dfc7}}pre{{background:#17253c;padding:24px;overflow:auto;
            border:1px solid #375270;border-radius:14px;line-height:1.6}}
            p{{line-height:1.7;max-width:760px}}</style><main>
            <small>PAYMENTS / DATA ENGINEERING / SYNTHETIC DATA</small>
            <h1>Settlement Recon</h1><p>Three payments. Two bank settlements.
            One matched payment, one partial payment and one missing settlement.
            This page queries the real reconciliation engine and verifies archived
            input checksums on each request.</p><pre>{evidence}</pre>
            <p>The invalid batch was quarantined through the same ingestion API.
            Repeated startup ingestion is idempotent. Administrative APIs require
            an operator token.</p><a href="/demo">Refresh from database</a> ·
            <a href="/demo/summary">Live JSON</a> · <a href="/docs">API documentation</a> ·
            <a href="https://github.com/9059Rohith/settlement-recon">Source</a>
            </main></html>"""

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
        try:
            with anyio.fail_after(10):
                async for chunk in request.stream():
                    if len(chunks) + len(chunk) > MAX_BYTES:
                        raise DomainError("Payload exceeds maximum size", "size")
                    chunks.extend(chunk)
        except TimeoutError:
            raise HTTPException(408, "Upload deadline exceeded") from None
        result = await run_in_threadpool(service.ingest, kind, source, bytes(chunks))
        ingestion.labels("replayed" if result["replayed"] else result["status"]).inc()
        return result

    @app.get("/v1/reconciliation", dependencies=[Depends(authenticate)])
    def reconciliation():
        return service.reconcile()

    @app.get(
        "/v1/reconciliation/{payment_id}/{currency}/explanation",
        dependencies=[Depends(authenticate)],
        tags=["Reconciliation evidence"],
        response_model=ReconciliationExplanation,
    )
    def explain(payment_id: str, currency: str, limit: Annotated[int, Query(ge=1, le=100)] = 25):
        return service.explain_payment(payment_id, currency, limit=limit)

    @app.get("/v1/batches", dependencies=[Depends(authenticate)])
    def list_batches():
        return service.batches()

    @app.get("/v1/batches/{batch_id}/verify", dependencies=[Depends(authenticate)])
    def verify(batch_id: str):
        return {"batch_id": batch_id, "intact": service.verify_archive(batch_id)}

    @app.get("/metrics", dependencies=[Depends(authenticate)], include_in_schema=False)
    def metrics():
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")

    @app.get(
        "/v1/forensics/case",
        dependencies=[Depends(authenticate)],
        response_model=ForensicsCase,
        tags=["Settlement Forensics"],
    )
    def investigation_case(
        source: str, payment_id: Annotated[list[str], Query(min_length=1, max_length=24)]
    ):
        return extract_case(service.engine, payment_id, source)

    install_forensics(app, authenticate)
    from settlement_recon.workspace import install

    install(app, service, authenticate, writer, demo_secret=token)
    return app


def from_environment() -> FastAPI:
    root = Path(os.environ.get("DATA_DIR", "data"))
    bucket = os.environ.get("RAW_BUCKET")
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
    if not database_url:
        root.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{root / 'recon.db'}"
    if isinstance(database_url, str) and database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    raw_store = os.environ.get("RAW_STORE", "s3" if bucket else "file")
    if raw_store == "database":
        from settlement_recon.database_archive import DatabaseArchive

        archive = DatabaseArchive(database_url)
    elif raw_store == "s3" and bucket:
        from settlement_recon.s3 import S3Archive

        archive = S3Archive(bucket, os.environ.get("RAW_KMS_KEY_ARN"))
    elif raw_store == "file":
        archive = FileArchive(root / "raw")
    else:
        raise ValueError("Invalid RAW_STORE configuration")
    service = Reconciler(database_url, archive)
    if os.environ.get("SEED_DEMO", "false").lower() == "true":
        from settlement_recon.demo import seed_demo

        seed_demo(service)
    return create_app(
        service,
        os.environ.get("API_TOKEN", ""),
        os.environ.get("READ_TOKEN", ""),
        public_demo=os.environ.get("PUBLIC_DEMO", "false").lower() == "true",
        allowed_hosts=[
            h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()
        ]
        or None,
    )
