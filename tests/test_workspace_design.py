"""Navigation, accessibility and asset boundaries for the redesigned workspace."""

from fastapi.testclient import TestClient

from settlement_recon.api import create_app
from settlement_recon.domain import FileArchive, Reconciler
from settlement_recon.workspace import PAGES


def test_every_page_has_keyboard_navigation_and_operator_boundary(tmp_path):
    app = create_app(
        Reconciler(f"sqlite:///{tmp_path / 'ui.db'}", FileArchive(tmp_path / "raw")),
        "ui-test-only-token-000000000000000000000",
    )
    with TestClient(app) as client:
        for page in PAGES:
            result = client.get("/workspace/" + page)
            assert result.status_code == 200
            assert 'id="command-palette"' in result.text
            assert 'aria-controls="workspace-navigation"' in result.text
            assert 'aria-current="page"' in result.text
            assert 'href="#main-content"' in result.text
        assert client.post("/workspace/api/rates/sync").status_code == 401
        assert client.get("/workspace/api/payments").status_code == 401
        assert 'id="currency-search"' in client.get("/workspace/overview").text
        assert 'id="currency-detail"' in client.get("/workspace/rates").text
        assert 'name="source"' in client.get("/workspace/converter").text
        assert 'name="target"' in client.get("/workspace/converter").text
        assert "font-src 'self'" in result.headers["content-security-policy"]


def test_bundled_font_is_real_and_delivered_same_origin(tmp_path):
    app = create_app(
        Reconciler(f"sqlite:///{tmp_path / 'ui.db'}", FileArchive(tmp_path / "raw")),
        "ui-test-only-token-000000000000000000000",
    )
    with TestClient(app) as client:
        result = client.get("/workspace/assets/manrope.ttf")
        assert result.status_code == 200
        assert result.content[:4] == b"\x00\x01\x00\x00"
        assert "font/ttf" in result.headers["content-type"]
