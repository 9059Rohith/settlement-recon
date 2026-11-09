"""As-of lookup and exact accounting invariants, including real ECB observations."""

import json
from datetime import date
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from settlement_recon.api import create_app
from settlement_recon.domain import FileArchive, Reconciler
from settlement_recon.history import Archive, load_archive


def request(**updates):
    return {
        "target_currency": "INR",
        "rounding_places": 2,
        "max_quote_age_days": 3,
        "records": [{"id": "invoice-1", "currency": "USD", "amount": "100", "date": "2025-01-05"}],
        **updates,
    }


def evaluate(payload, archive=None):
    from settlement_recon.fixing import FixingRequest, value_at_fixing

    return value_at_fixing(archive or load_archive(), FixingRequest.model_validate(payload))


def test_weekend_uses_prior_real_quote_and_never_future_quote():
    result = evaluate(request())
    row = result["records"][0]
    assert result["status"] == "complete"
    assert row["quote_date"] == "2025-01-03" and row["quote_age_days"] == 2
    archive = load_archive()
    idx = archive.dates.index(date(2025, 1, 3))
    quotes = archive.rows[idx]
    expected = Fraction(quotes[archive.currencies.index("INR")]) / Fraction(
        quotes[archive.currencies.index("USD")]
    )
    assert Fraction(row["rate_numerator"], row["rate_denominator"]) == expected
    assert Fraction(row["value_numerator"], row["value_denominator"]) == 100 * expected
    assert result["source"]["archive_sha256"] == archive.archive_sha256


def test_stale_or_missing_quotes_do_not_publish_a_complete_total():
    stale = evaluate(request(max_quote_age_days=1))
    assert stale["records"][0]["status"] == "stale"
    assert stale["complete_total"] is None and stale["valued_count"] == 0
    assert stale["status"] == "incomplete"
    missing = evaluate(
        request(records=[{"id": "x", "currency": "USD", "amount": "1", "date": "1998-12-31"}])
    )
    assert missing["records"][0]["status"] == "unavailable"


def test_exact_half_even_and_row_vs_aggregate_rounding_are_distinct():
    # A small in-test archive is a mathematical oracle, never public demo data.
    archive = Archive((date(2025, 1, 2),), ("EUR", "USD"), (("1", "2"),), "a" * 64, "b" * 64)
    rows = [
        {"id": str(i), "currency": "USD", "amount": "0.01", "date": "2025-01-02"} for i in range(3)
    ]
    result = evaluate(request(target_currency="EUR", records=rows), archive)
    assert [r["rounded_value"] for r in result["records"]] == ["0.00"] * 3
    assert result["sum_rounded_rows"] == "0.00"
    assert result["rounded_exact_subtotal"] == result["complete_total"] == "0.02"
    assert result["rounding_difference"] == "0.02"


def test_missing_currency_observation_uses_last_available_pair_not_latest_day():
    archive = Archive(
        (date(2025, 1, 2), date(2025, 1, 3)),
        ("EUR", "USD"),
        (("1", "2"), ("1", "N/A")),
        "a" * 64,
        "b" * 64,
    )
    result = evaluate(request(target_currency="EUR"), archive)
    assert result["records"][0]["quote_date"] == "2025-01-02"
    assert result["records"][0]["quote_age_days"] == 3


def test_identity_needs_no_quote_and_mixed_results_keep_subtotal_labeled():
    result = evaluate(
        request(
            records=[
                {"id": "same", "currency": "INR", "amount": "1.234", "date": "2025-01-05"},
                {"id": "old", "currency": "USD", "amount": "100", "date": "1998-01-01"},
            ]
        )
    )
    assert result["valued_count"] == 1 and result["unvalued_count"] == 1
    assert result["records"][0]["quote_date"] is None
    assert result["records"][0]["method"] == "identity"
    assert result["rounded_exact_subtotal"] == "1.23" and result["complete_total"] is None


def test_report_fingerprint_is_deterministic_and_changes_with_policy():
    a, b = evaluate(request()), evaluate(request())
    assert a == b and len(a["report_sha256"]) == 64
    assert a["report_sha256"] != evaluate(request(rounding_places=3))["report_sha256"]


@pytest.mark.parametrize(
    "updates",
    [
        {"rounding_places": True},
        {"rounding_places": 7},
        {"max_quote_age_days": 11},
        {"target_currency": "ZZZ"},
        {"records": []},
        {"records": [{"id": "x", "currency": "USD", "amount": 1, "date": "2025-01-02"}]},
        {"records": [{"id": "x", "currency": "USD", "amount": "0", "date": "2025-01-02"}]},
        {"records": [{"id": "x", "currency": "USD", "amount": "NaN", "date": "2025-01-02"}]},
    ],
)
def test_invalid_inputs_fail_closed(updates):
    with pytest.raises(ValueError):
        evaluate(request(**updates))


def test_duplicate_ids_and_oversized_workloads_rejected():
    with pytest.raises(ValueError):
        evaluate(request(records=request()["records"] * 2))
    with pytest.raises(ValueError):
        evaluate(request(records=[{**request()["records"][0], "id": f"x{i}"} for i in range(51)]))


def test_public_endpoint_is_bounded_no_auth_or_database_capture_required(tmp_path):
    service = Reconciler(f"sqlite:///{tmp_path / 'fixing.db'}", FileArchive(tmp_path / "raw"))
    with TestClient(create_app(service, "test-fixing-token-00000000000000000000000")) as client:
        response = client.post("/workspace/api/fixing", json=request())
        assert response.status_code == 200 and response.json()["status"] == "complete"
        assert response.headers["cache-control"] == "no-store"
        assert (
            client.post(
                "/workspace/api/fixing",
                json=request(),
                headers={"origin": "https://foreign.example"},
            ).status_code
            == 403
        )
        assert client.post("/workspace/api/fixing", content="x" * 32769).status_code == 413
        raw = json.dumps(request()).replace(
            '"rounding_places": 2', '"rounding_places": 2, "rounding_places": 0'
        )
        assert client.post("/workspace/api/fixing", content=raw).status_code == 422
        assert client.post("/workspace/api/fixing", content="[" * 10000).status_code == 422
        assert client.get("/workspace/api/payments").status_code == 401
        document = client.get("/workspace/history")
        assert 'id="fixing-form"' in document.text
        assert client.get("/workspace/assets/fixing.js").status_code == 200
