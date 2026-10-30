"""Allocations are judged against expected outcomes and an independent tiny oracle."""

import itertools
import json
import random

import pytest
from fastapi.testclient import TestClient


def analyze(payments, legs, **policy):
    from settlement_recon.forensics import analyze as run

    return run({"payments": payments, "legs": legs, "policy": policy})


def payment(identity="p1", amount=100, currency="USD", **extra):
    return {"payment_id": identity, "amount_minor": amount, "currency": currency, **extra}


def leg(identity="l1", amount=100, currency="USD", **extra):
    return {"leg_id": identity, "net_minor": amount, "fee_minor": 0, "currency": currency, **extra}


def decisions(report):
    return {value["payment_id"]: value for value in report["decisions"]}


def test_exact_assignment_has_a_reproducible_complete_certificate():
    report = analyze([payment()], [leg()])
    assert report["complete"] and report["advisory_only"]
    assert report["suggestions"][0]["leg_ids"] == ["l1"]
    assert report["suggestions"][0]["difference_minor"] == 0
    assert decisions(report)["p1"]["status"] == "unique"
    assert report["components"][0]["optimal_allocations"] == 1
    assert len(report["request_sha256"]) == len(report["policy_sha256"]) == 64


def test_split_settlement_uses_net_plus_fees_and_preserves_reference_evidence():
    report = analyze(
        [payment(reference="INVOICE-101")],
        [
            leg("l1", 59, fee_minor=1, reference="invoice 101"),
            leg("l2", 39, fee_minor=1, reference="INVOICE101"),
        ],
    )
    row = report["suggestions"][0]
    assert row["leg_ids"] == ["l1", "l2"] and row["settled_minor"] == 100
    assert row["reference_evidence"] == "exact"


def test_global_optimization_never_reuses_a_leg():
    report = analyze(
        [payment("p1", 100), payment("p2", 60)], [leg("a", 60), leg("b", 40), leg("c", 100)]
    )
    assert {row["payment_id"]: row["leg_ids"] for row in report["suggestions"]} == {
        "p1": ["c"],
        "p2": ["a"],
    }


def test_equal_amount_collisions_abstain_instead_of_breaking_ties_by_identifier():
    report = analyze([payment("p1"), payment("p2")], [leg("a"), leg("b")])
    assert report["suggestions"] == []
    assert all(row["status"] == "ambiguous" for row in report["decisions"])
    assert report["components"][0]["optimal_allocations"] == 2


def test_competition_between_matched_and_unmatched_is_also_ambiguous():
    report = analyze([payment("p1"), payment("p2")], [leg()])
    assert report["suggestions"] == []
    assert all(row["status"] == "ambiguous" for row in report["decisions"])
    assert all(None in row["alternatives"] for row in report["decisions"])


def test_currency_never_matches_even_when_numeric_values_are_identical():
    report = analyze([payment()], [leg(currency="EUR")])
    assert decisions(report)["p1"]["status"] == "unmatched"
    assert not report["suggestions"]


def test_reference_conflict_default_and_explicit_relaxation_are_distinct():
    p, bank = [payment(reference="A")], [leg(reference="B")]
    assert not analyze(p, bank)["suggestions"]
    relaxed = analyze(p, bank, require_reference_agreement=False)
    assert relaxed["suggestions"][0]["reference_evidence"] == "conflict_allowed"


def test_complete_reference_policy_abstains_when_identity_evidence_is_missing():
    result = analyze([payment()], [leg()], require_complete_reference=True)
    assert not result["suggestions"]
    result = analyze(
        [payment(reference="A")], [leg(reference="A")], require_complete_reference=True
    )
    assert result["suggestions"][0]["reference_evidence"] == "exact"


def test_reference_preference_and_date_window_are_explicit_not_probabilities():
    report = analyze(
        [payment(reference="A", expected_on="2026-10-01")],
        [
            leg("a", reference="A", settled_on="2026-10-02"),
            leg("b", settled_on="2026-10-01"),
            leg("c", reference="A", settled_on="2026-11-01"),
        ],
        max_lag_days=3,
    )
    assert report["suggestions"][0]["leg_ids"] == ["a"]
    assert report["suggestions"][0]["max_lag_days"] == 1
    assert "probability" not in report["suggestions"][0]


def test_tolerance_does_not_silently_change_amounts():
    report = analyze([payment()], [leg(amount=101)], tolerance_minor=1)
    assert report["suggestions"][0]["difference_minor"] == -1
    assert not analyze([payment()], [leg(amount=101)])["suggestions"]


def test_input_permutation_does_not_change_decisions_or_digest():
    p, bank = [payment("a"), payment("b", 200)], [leg("x"), leg("y", 200)]
    first, second = analyze(p, bank), analyze(p[::-1], bank[::-1])
    for key in ["request_sha256", "policy_sha256", "decisions", "suggestions", "components"]:
        assert first[key] == second[key]


@pytest.mark.parametrize("bad", [True, 1.5, "100", -1, 10**15 + 1])
def test_amounts_reject_coercion_and_invalid_ranges(bad):
    with pytest.raises(ValueError):
        analyze([payment(amount=bad)], [leg()])


def test_duplicate_identifiers_and_unknown_fields_are_rejected():
    with pytest.raises(ValueError):
        analyze([payment(), payment()], [leg()])
    with pytest.raises(ValueError):
        analyze([payment(password="private")], [leg()])
    with pytest.raises(ValueError):
        analyze([payment()], [leg(), leg()])


def test_search_exhaustion_cannot_claim_complete_or_recommend_a_partial_optimum():
    report = analyze([payment("p1"), payment("p2")], [leg("a"), leg("b")], max_states=1)
    assert not report["complete"] and not report["suggestions"]
    assert {row["status"] for row in report["decisions"]} == {"budget_exceeded"}


def test_oversized_connected_component_abstains_but_independent_one_still_works():
    report = analyze(
        [payment(f"p{i}") for i in range(11)] + [payment("safe", 999)],
        [leg(f"l{i}") for i in range(11)] + [leg("safe-leg", 999)],
        max_split=1,
    )
    assert not report["complete"]
    assert report["suggestions"][0]["payment_id"] == "safe"
    assert decisions(report)["p0"]["status"] == "capacity_exceeded"


def test_small_amount_only_problem_agrees_with_independent_exhaustive_oracle():
    generator = random.Random(20261030)
    for _ in range(40):
        p = [payment(f"p{i}", generator.choice([100, 200, 300])) for i in range(3)]
        bank = [leg(f"l{i}", generator.choice([100, 200, 400])) for i in range(4)]
        choices = [
            [None] + [b["leg_id"] for b in bank if b["net_minor"] == row["amount_minor"]]
            for row in p
        ]
        allocations = [
            combo
            for combo in itertools.product(*choices)
            if len([v for v in combo if v is not None]) == len({v for v in combo if v is not None})
        ]
        maximum = max(sum(v is not None for v in combo) for combo in allocations)
        best = [combo for combo in allocations if sum(v is not None for v in combo) == maximum]
        result = analyze(p, bank, max_split=1)
        expected = {}
        for index, row in enumerate(p):
            possible = {combo[index] for combo in best}
            expected[row["payment_id"]] = (
                "ambiguous"
                if len(possible) > 1
                else ("unmatched" if possible == {None} else "unique")
            )
        assert {key: value["status"] for key, value in decisions(result).items()} == expected


@pytest.fixture
def client(tmp_path):
    from settlement_recon.api import create_app
    from settlement_recon.domain import FileArchive, Reconciler

    service = Reconciler(f"sqlite:///{tmp_path / 'api.db'}", FileArchive(tmp_path / "raw"))
    app = create_app(
        service,
        "forensics-operator-token-0000000000000000",
        "forensics-reader-token-000000000000000000",
    )
    with TestClient(app) as value:
        yield value


def authorization(reader=False):
    role = "reader" if reader else "operator"
    return {
        "Authorization": f"Bearer forensics-{role}-token-"
        + ("000000000000000000" if reader else "0000000000000000")
    }


def test_protected_forensics_supports_reader_without_creating_business_rows(client):
    path = "/v1/forensics/analyze"
    body = {"payments": [payment()], "legs": [leg()]}
    assert client.post(path, json=body).status_code == 401
    before = client.get("/v1/batches", headers=authorization()).json()
    response = client.post(path, json=body, headers=authorization(reader=True))
    assert response.status_code == 200, response.text
    assert response.json()["suggestions"][0]["leg_ids"] == ["l1"]
    assert client.get("/v1/batches", headers=authorization()).json() == before


def test_forensics_openapi_has_typed_request_and_response(client):
    route = client.get("/openapi.json").json()["paths"]["/v1/forensics/analyze"]["post"]
    assert route["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "ForensicsRequest"
    )
    assert route["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "ForensicsReport"
    )


def test_invalid_body_never_reflects_private_values(client):
    secret = "REVIEW-PRIVATE-INPUT-MUST-NOT-BE-REFLECTED"
    response = client.post(
        "/v1/forensics/analyze",
        headers=authorization(),
        json={"payments": [payment(password=secret)], "legs": []},
    )
    assert response.status_code == 422
    assert secret not in response.text


def test_size_depth_duplicate_keys_and_unsupported_media_fail_safely(client):
    path = "/v1/forensics/analyze"
    auth = {**authorization(), "Content-Type": "application/json"}
    assert client.post(path, content=b" " * 128_001, headers=auth).status_code == 413
    assert client.post(path, content=b"[" * 20 + b"0" + b"]" * 20, headers=auth).status_code == 422
    assert (
        client.post(
            path, content=b'{"payments":[],"payments":[],"legs":[]}', headers=auth
        ).status_code
        == 422
    )
    assert (
        client.post(
            path, content=b"anything", headers={**authorization(), "Content-Type": "text/plain"}
        ).status_code
        == 415
    )


@pytest.mark.anyio
async def test_unauthorized_request_does_not_consume_or_wait_for_the_body(tmp_path):
    from settlement_recon.api import create_app
    from settlement_recon.domain import FileArchive, Reconciler

    app = create_app(
        Reconciler(f"sqlite:///{tmp_path / 'guard.db'}", FileArchive(tmp_path / "raw")),
        "forensics-operator-token-0000000000000000",
    )
    touched = []
    sent = []

    async def receive():
        touched.append(True)
        return {"type": "http.request", "body": b"malformed", "more_body": False}

    async def send(message):
        sent.append(message)

    await app(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/forensics/analyze",
            "headers": [],
            "query_string": b"",
            "http_version": "1.1",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1),
        },
        receive,
        send,
    )
    assert not touched
    assert next(value["status"] for value in sent if value["type"] == "http.response.start") == 401


def test_cli_reads_a_bounded_case_without_requiring_or_initializing_a_database(
    tmp_path, monkeypatch, capsys
):
    from settlement_recon.cli import main

    case = tmp_path / "case.json"
    case.write_text(json.dumps({"payments": [payment()], "legs": [leg()]}))
    monkeypatch.setenv("DATABASE_URL", "deliberately-unavailable://must-not-connect")
    monkeypatch.setattr("sys.argv", ["settlement-recon", "forensics", str(case)])
    main()
    assert json.loads(capsys.readouterr().out)["suggestions"][0]["payment_id"] == "p1"


def test_candidate_enumeration_budget_cannot_publish_a_partial_candidate_universe():
    result = analyze([payment(f"p{i}", 2) for i in range(24)], [leg(f"l{i}", 1) for i in range(32)])
    assert not result["complete"] and not result["suggestions"]
    assert result["components"][0]["status"] == "budget_exceeded"


def test_count_capping_does_not_hide_ambiguity():
    result = analyze(
        [payment(f"p{i}") for i in range(10)], [leg(f"l{i}") for i in range(10)], max_split=1
    )
    assert result["complete"] and not result["suggestions"]
    assert result["components"][0]["optimal_allocations"] == 1_000_000
    assert result["components"][0]["allocation_count_capped"]
    assert all(value["alternatives_truncated"] for value in result["decisions"])


def test_capacity_limit_releases_its_slot_after_success(client):
    slots = client.app.state.forensics_slots
    assert slots.acquire(False) and slots.acquire(False)
    body = {"payments": [payment()], "legs": [leg()]}
    try:
        response = client.post("/v1/forensics/analyze", json=body, headers=authorization())
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "2"
    finally:
        slots.release()
        slots.release()
    assert (
        client.post("/v1/forensics/analyze", json=body, headers=authorization()).status_code == 200
    )


@pytest.mark.anyio
async def test_authenticated_slow_upload_has_a_deadline(tmp_path, monkeypatch):
    import anyio

    from settlement_recon.api import create_app
    from settlement_recon.domain import FileArchive, Reconciler

    monkeypatch.setattr("settlement_recon.forensics_http.READ_SECONDS", 0.02)
    app = create_app(
        Reconciler(f"sqlite:///{tmp_path / 'slow.db'}", FileArchive(tmp_path / "raw")),
        "forensics-operator-token-0000000000000000",
    )
    sent = []

    async def receive():
        await anyio.sleep(0.2)
        return {"type": "http.request", "body": b"{}", "more_body": False}

    async def send(message):
        sent.append(message)

    headers = [
        (b"authorization", authorization()["Authorization"].encode()),
        (b"content-type", b"application/json"),
    ]
    await app(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/forensics/analyze",
            "headers": headers,
            "query_string": b"",
            "http_version": "1.1",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1),
        },
        receive,
        send,
    )
    assert next(value["status"] for value in sent if value["type"] == "http.response.start") == 408
