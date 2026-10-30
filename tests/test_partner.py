import json

import httpx
import pytest

from settlement_recon.domain import DomainError, FileArchive, Reconciler
from settlement_recon.partner import pull_partner


def test_partner_fetch_is_bounded_authenticated_and_replay_safe(tmp_path):
    service = Reconciler(f"sqlite:///{tmp_path / 'test.db'}", FileArchive(tmp_path / "raw"))
    calls = []

    def handler(request):
        calls.append(request.headers.get("Authorization"))
        return httpx.Response(
            200, json={"payments": [{"payment_id": "p1", "currency": "USD", "amount": "10.00"}]}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = pull_partner(
            service,
            "https://partner.test/payments",
            "external-token",
            {"partner.test"},
            client=client,
        )
        second = pull_partner(
            service,
            "https://partner.test/payments",
            "external-token",
            {"partner.test"},
            client=client,
        )
    assert first["status"] == "accepted"
    assert second["replayed"]
    assert calls == ["Bearer external-token"] * 2


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://evil.test/x",
        "https://user:password@partner.test/x",
        "http://partner.test/x",
    ],
)
def test_untrusted_partner_endpoints_are_rejected(tmp_path, url):
    service = Reconciler(f"sqlite:///{tmp_path / 'test.db'}", FileArchive(tmp_path / "raw"))
    with pytest.raises(DomainError):
        pull_partner(service, url, "token", {"partner.test"})


def test_partner_retries_transient_errors_only(tmp_path):
    service = Reconciler(f"sqlite:///{tmp_path / 'test.db'}", FileArchive(tmp_path / "raw"))
    attempts = []

    def handler(request):
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(503)
        return httpx.Response(
            200,
            content=json.dumps(
                {"payments": [{"payment_id": "p1", "currency": "USD", "amount": "1"}]}
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert (
            pull_partner(
                service,
                "https://partner.test/x",
                "token",
                {"partner.test"},
                client=client,
                sleep=lambda _: None,
            )["status"]
            == "accepted"
        )
    assert len(attempts) == 3
