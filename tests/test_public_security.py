import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from settlement_recon.api import create_app
from settlement_recon.domain import FileArchive, Reconciler

TOKEN = "test-token-00000000000000000000000000"


@pytest.mark.parametrize(
    "deployment,hosted,accepted",
    [
        ("recon-preview-123.vercel.app", "1", True),
        ("recon-preview-123.vercel.app", "0", False),
        ("other.example", "1", False),
        ("*.vercel.app", "1", False),
        ("https://recon-preview-123.vercel.app/path", "1", False),
    ],
)
def test_staged_vercel_host_is_exact_and_platform_scoped(
    tmp_path, monkeypatch, deployment, hosted, accepted
):
    monkeypatch.setenv("VERCEL", hosted)
    monkeypatch.setenv("VERCEL_URL", deployment)
    service = Reconciler(f"sqlite:///{tmp_path / 'host.db'}", FileArchive(tmp_path / "raw"))
    configured = ["recon.example"]
    app = create_app(service, TOKEN, allowed_hosts=configured)
    with TestClient(app) as client:
        assert client.get("/healthz", headers={"Host": "recon.example"}).status_code == 200
        assert client.get("/healthz", headers={"Host": deployment}).status_code == (
            200 if accepted else 400
        )
        assert client.get("/healthz", headers={"Host": "unrelated.vercel.app"}).status_code == 400
    assert configured == ["recon.example"]


def test_unauthenticated_upload_does_not_consume_request_body(tmp_path):
    service = Reconciler(f"sqlite:///{tmp_path / 'security.db'}", FileArchive(tmp_path / "raw"))
    app = create_app(service, TOKEN)
    consumed = False

    async def run():
        async def content():
            nonlocal consumed
            consumed = True
            yield b"unauthenticated upload must not be read"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            result = await client.post("/v1/ingest/payments?source=x", content=content())
            assert result.status_code == 401

    asyncio.run(run())
    assert not consumed


def test_slow_authenticated_upload_has_deadline(tmp_path, monkeypatch):
    import settlement_recon.api as module

    original = module.anyio.fail_after
    monkeypatch.setattr(module.anyio, "fail_after", lambda _seconds: original(0.02))
    service = Reconciler(f"sqlite:///{tmp_path / 'slow.db'}", FileArchive(tmp_path / "raw"))
    app = create_app(service, TOKEN)

    async def run():
        async def content():
            yield b"{"
            await asyncio.sleep(1)
            yield b"}"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            result = await client.post(
                "/v1/ingest/payments?source=x",
                content=content(),
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
            assert result.status_code == 408

    asyncio.run(run())
    assert service.batches() == []


def test_documentation_bootstrap_is_explicitly_authorized(tmp_path):
    service = Reconciler(f"sqlite:///{tmp_path / 'docs.db'}", FileArchive(tmp_path / "raw"))
    with TestClient(create_app(service, TOKEN)) as client:
        response = client.get("/docs")
    assert response.status_code == 200
    policy = response.headers["Content-Security-Policy"]
    assert "'unsafe-inline'" not in policy.split("script-src", 1)[1].split(";")[0]
    assert "'sha256-" in policy
    assert "connect-src 'self'" in policy
