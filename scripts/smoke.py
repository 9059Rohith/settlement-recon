"""Real HTTP acceptance against a running service, using only synthetic records."""

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    args = parser.parse_args()
    token = os.environ["API_TOKEN"]
    prefix = "smoke-" + uuid4().hex
    with httpx.Client(base_url=args.url, timeout=15, trust_env=False) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/v1/batches").status_code == 401
        assert (
            client.get("/v1/batches", headers={b"Authorization": b"Bearer \xff\xfe"}).status_code
            == 401
        )
        headers = {"Authorization": f"Bearer {token}"}
        body = json.dumps(
            {"payments": [{"payment_id": prefix, "currency": "USD", "amount": "100.00"}]}
        ).encode()
        first = client.post(
            "/v1/ingest/payments", params={"source": "http-smoke"}, content=body, headers=headers
        )
        first.raise_for_status()
        assert first.json()["status"] == "accepted"
        repeated = client.post(
            "/v1/ingest/payments", params={"source": "http-smoke"}, content=body, headers=headers
        )
        assert repeated.json()["replayed"]
        statement = (
            "row_id,payment_id,currency,net_amount,fee,settled_at\n"
            f"{prefix},{prefix},USD,99,1,2026-10-30T10:00:00Z\n"
        ).encode()
        result = client.post(
            "/v1/ingest/statement",
            params={"source": "http-smoke"},
            content=statement,
            headers=headers,
        )
        result.raise_for_status()
        assert result.json()["status"] == "accepted"
        rows = client.get("/v1/reconciliation", headers=headers).json()
        match = next(r for r in rows if r["payment_id"] == prefix)
        assert match["status"] == "matched" and match["settled_minor"] == 10000
        bad = client.post(
            "/v1/ingest/statement", params={"source": prefix}, content=b"corrupt", headers=headers
        )
        assert bad.json()["status"] == "quarantined"
        verification = client.get(f"/v1/batches/{first.json()['batch_id']}/verify", headers=headers)
        assert verification.json()["intact"]
        assert "settlement_recon_http_seconds" in client.get("/metrics", headers=headers).text
    report = {
        "url": args.url,
        "health": True,
        "database_ready": True,
        "openapi": True,
        "auth_denied": True,
        "non_ascii_auth_denied": True,
        "idempotent_replay": True,
        "exact_match_with_fee": True,
        "quarantine": True,
        "archive_verified": True,
        "metrics": True,
        "synthetic_payment_id": prefix,
    }
    Path("evidence/http-smoke.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
