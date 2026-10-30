"""Authenticate before consuming an investigation body; bound parse and compute work."""

import json
import threading

import anyio
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from settlement_recon.forensics import analyze
from settlement_recon.forensics_models import ForensicsReport, ForensicsRequest

FORENSICS_PATH = "/v1/forensics/analyze"
BODY_LIMIT = 128_000
READ_SECONDS = 5.0
MAX_DEPTH = 8
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate object key")
        result[key] = value
    return result


def load_case(raw):
    """Depth is checked before recursion in the JSON parser; strings are opaque."""
    depth = 0
    quoted = False
    escaped = False
    for character in raw.decode("utf-8"):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError("Investigation structure exceeds its depth limit")
        elif character in "]}":
            depth -= 1
    value = json.loads(raw, object_pairs_hook=unique_object)
    return ForensicsRequest.model_validate(value)


class ForensicsGuard:
    """A pure ASGI body guard; other application routes keep their own contracts."""

    def __init__(self, app, authenticate):
        self.app = app
        self.authenticate = authenticate

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != FORENSICS_PATH:
            await self.app(scope, receive, send)
            return
        if scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
        credentials = (
            HTTPAuthorizationCredentials(scheme=scheme, credentials=supplied)
            if scheme.lower() == "bearer" and supplied
            else None
        )
        try:
            self.authenticate(credentials)
        except HTTPException as error:
            await self.reject(scope, receive, send, error.status_code, error.detail, error.headers)
            return
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            await self.reject(scope, receive, send, 415, "Use application/json")
            return
        length = request.headers.get("content-length")
        if length is not None:
            if not length.isascii() or not length.isdecimal():
                await self.reject(scope, receive, send, 400, "Invalid content length")
                return
            if len(length) > 12 or int(length) > BODY_LIMIT:
                await self.reject(scope, receive, send, 413, "Investigation body exceeds limit")
                return
        body = bytearray()
        try:
            with anyio.fail_after(READ_SECONDS):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > BODY_LIMIT:
                        await self.reject(
                            scope, receive, send, 413, "Investigation body exceeds limit"
                        )
                        return
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await self.reject(scope, receive, send, 408, "Investigation upload deadline exceeded")
            return
        try:
            load_case(bytes(body))
        except (ValueError, UnicodeError, RecursionError):
            await self.reject(scope, receive, send, 422, "Invalid bounded investigation request")
            return
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def reject(scope, receive, send, status, detail, headers=None):
        response = JSONResponse(
            {"detail": detail}, status, headers={**SECURITY_HEADERS, **(headers or {})}
        )
        await response(scope, receive, send)


def install(app, authenticate):
    app.add_middleware(ForensicsGuard, authenticate=authenticate)
    app.state.forensics_slots = threading.BoundedSemaphore(2)

    @app.post(
        FORENSICS_PATH,
        response_model=ForensicsReport,
        dependencies=[Depends(authenticate)],
        tags=["Settlement Forensics"],
    )
    def investigate(body: ForensicsRequest):
        if not app.state.forensics_slots.acquire(blocking=False):
            raise HTTPException(
                429, "Investigation capacity reached; retry later", headers={"Retry-After": "2"}
            )
        try:
            return analyze(body)
        finally:
            app.state.forensics_slots.release()
