"""Atomic database-backed anonymous AI budgets; no raw client addresses are retained."""

import hashlib
import hmac
import ipaddress
import os
import time

from fastapi import HTTPException, Request
from sqlalchemy import Column, Integer, MetaData, String, Table, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from settlement_recon.schema import initialize_schema

metadata = MetaData()
buckets = Table(
    "workspace_public_ai_budgets",
    metadata,
    Column("key", String(120), primary_key=True),
    Column("count", Integer, nullable=False),
    Column("expires", Integer, nullable=False),
)


def client_identity(request: Request) -> str:
    # Only the actual Vercel deployment may trust its overwritten forwarding header.
    candidate = request.client.host if request.client else "unknown"
    if os.getenv("VERCEL") == "1":
        forwarded = request.headers.get("x-vercel-forwarded-for") or request.headers.get(
            "x-forwarded-for", ""
        )
        try:
            candidate = str(ipaddress.ip_address(forwarded.strip()))
        except ValueError:
            # A malformed/missing header shares a conservative bucket; it cannot bypass limits.
            candidate = "unknown-vercel-client"
    return candidate


def same_origin(request: Request, *, max_bytes: int = 4096) -> None:
    origin = request.headers.get("origin")
    allowed = {str(request.base_url).rstrip("/")}
    if os.getenv("VERCEL") == "1":
        allowed.add("https://" + request.url.netloc)
    if origin is not None and origin not in allowed:
        raise HTTPException(403, "Recruiter demo requires a same-origin request")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site demo requests are not allowed")
    try:
        size = int(request.headers.get("content-length", "0"))
    except ValueError as exc:
        raise HTTPException(400, "Invalid request length") from exc
    if size > max_bytes:
        raise HTTPException(413, "Demo request exceeds allowed size")


class DemoBudget:
    def __init__(self, engine, secret: str):
        self.engine, self.secret = engine, secret
        initialize_schema(engine, metadata)

    def consume(self, address: str, *, now: int | None = None) -> None:
        if len(self.secret) < 32:
            raise HTTPException(503, "Public demo privacy configuration is unavailable")
        if os.getenv("VERCEL") == "1" and self.engine.dialect.name != "postgresql":
            raise HTTPException(503, "Public demo requires its durable rate-limit database")
        now = int(time.time()) if now is None else now
        identity = hmac.new(self.secret.encode(), address.encode(), hashlib.sha256).hexdigest()
        windows = [
            ("global-day", 86400, 30),
            ("global-minute", 60, 2),
            ("client-" + identity, 600, 3),
        ]
        insert = pg_insert if self.engine.dialect.name == "postgresql" else sqlite_insert
        try:
            with self.engine.begin() as conn:
                for name, seconds, limit in windows:
                    expiry = (now // seconds + 1) * seconds
                    key = f"{name}:{now // seconds}"
                    statement = insert(buckets).values(key=key, count=1, expires=expiry)
                    count = conn.execute(
                        statement.on_conflict_do_update(
                            index_elements=[buckets.c.key],
                            set_={"count": buckets.c.count + 1},
                            where=buckets.c.count < limit,
                        ).returning(buckets.c.count)
                    ).scalar_one_or_none()
                    if count is None:
                        raise HTTPException(
                            429,
                            "Free recruiter demo limit reached. Please retry after the cooldown.",
                            headers={
                                "Retry-After": str(max(1, expiry - now)),
                                "Cache-Control": "no-store",
                            },
                        )
                conn.execute(delete(buckets).where(buckets.c.expires < now - 86400))
        except SQLAlchemyError as exc:
            raise HTTPException(
                503,
                "Demo rate-limit storage is unavailable; no AI request was made",
                headers={"Retry-After": "60"},
            ) from exc
