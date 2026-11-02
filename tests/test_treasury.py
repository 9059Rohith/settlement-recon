"""Hand-calculated risk cases, independent of implementation helpers."""

import hashlib
import json
from decimal import ROUND_DOWN, Decimal, localcontext

import pytest
from pydantic import ValidationError


def request_data():
    return {
        "reporting_currency": "EUR",
        "positions": [
            {"id": "invoice", "currency": "USD", "direction": "receivable", "amount": "100"},
            {"id": "vendor", "currency": "USD", "direction": "payable", "amount": "60"},
            {"id": "reserve", "currency": "GBP", "direction": "receivable", "amount": "10"},
        ],
        "scenarios": [{"name": "Dollar falls", "shocks_bps": {"USD": -1000, "GBP": 2000}}],
        "net_limit": "41",
    }


def snapshot():
    return {
        "status": "captured",
        "digest": "a" * 64,
        "captured_at": "2026-11-01T18:13:31Z",
        "source": "https://api.frankfurter.dev/v1/latest",
        "observation": {"base": "EUR", "date": "2026-10-30", "rates": {"USD": 2, "GBP": 0.5}},
    }


def run(data=None):
    from settlement_recon.treasury import StressRequest, analyze

    return analyze(snapshot(), StressRequest.model_validate(data or request_data()))


def test_inverse_quote_netting_and_gross_concentration():
    report = run()
    assert report["baseline"]["receivables"] == "70"
    assert report["baseline"]["payables"] == "30"
    assert report["baseline"]["net"] == "40"
    assert report["baseline"]["gross"] == "100"
    assert report["baseline"]["gross_concentration_hhi"] == "0.68"
    usd = next(row for row in report["exposures"] if row["currency"] == "USD")
    assert usd["net_native"] == "40"
    assert usd["net_reporting"] == "20"
    assert usd["gross_share"] == "0.8"


def test_scenario_offsets_and_absolute_limit_are_not_probability_claims():
    report = run()
    assert report["baseline"]["limit_breached"] is False
    scenario = report["scenarios"][0]
    assert scenario["net"] == "42"
    assert scenario["delta"] == "2"
    assert scenario["limit_breached"] is True
    assert report["worst_loss"] == "0"
    assert report["method"]["kind"] == "deterministic_hypothetical_stress"
    assert report["source"]["digest"] == "a" * 64


def test_reporting_currency_has_no_self_fx_risk():
    data = request_data()
    data["reporting_currency"] = "GBP"
    data["scenarios"][0]["shocks_bps"] = {"USD": -1000}
    report = run(data)
    assert report["baseline"]["net"] == "20"
    assert report["scenarios"][0]["net"] == "19"
    assert report["scenarios"][0]["delta"] == "-1"
    assert report["worst_loss"] == "1"


def test_decimal_context_is_isolated_and_zero_net_does_not_divide_by_zero():
    data = request_data()
    data["positions"] = [
        {"id": "a", "currency": "USD", "direction": "receivable", "amount": "999999999999.000001"},
        {"id": "b", "currency": "USD", "direction": "payable", "amount": "999999999999.000001"},
    ]
    with localcontext() as context:
        context.prec = 6
        report = run(data)
        assert context.prec == 6
    assert report["baseline"]["net"] == "0"
    assert report["baseline"]["gross"] == "999999999999.000001"
    assert report["baseline"]["gross_concentration_hhi"] == "1"
    assert report["scenarios"][0]["delta"] == "0"


def test_report_is_reproducible_and_fingerprint_covers_results():
    report = run()
    assert report == run()
    digest = report.pop("report_digest")
    raw = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert hashlib.sha256(raw.encode()).hexdigest() == digest
    assert Decimal(report["scenarios"][0]["contributions"][0]["delta"]) == 4
    assumptions = report["assumptions"]
    raw_request = json.dumps(assumptions, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert hashlib.sha256(raw_request.encode()).hexdigest() == report["request_digest"]
    assert assumptions["positions"][0]["amount"] == "100"


def test_caller_rounding_does_not_change_report_or_create_zero_shock_loss():
    from settlement_recon.treasury import StressRequest, analyze

    source = snapshot()
    source["observation"]["rates"]["USD"] = 3
    data = request_data()
    data["scenarios"][0]["shocks_bps"] = {"USD": 0}
    expected = analyze(source, StressRequest.model_validate(data))
    with localcontext() as context:
        context.rounding = ROUND_DOWN
        observed = analyze(source, StressRequest.model_validate(data))
    assert observed == expected
    assert observed["scenarios"][0]["delta"] == "0"


@pytest.mark.parametrize(
    "amount", ["NaN", "Infinity", "1e3", "-1", "0", "01", "1.0000001", "1000000000001", 100]
)
def test_noncanonical_or_out_of_bounds_money_is_rejected(amount):
    from settlement_recon.treasury import StressRequest

    data = request_data()
    data["positions"][0]["amount"] = amount
    with pytest.raises(ValidationError):
        StressRequest.model_validate(data)


@pytest.mark.parametrize(
    "change",
    [
        "duplicate_position",
        "duplicate_scenario",
        "float_shock",
        "unknown_field",
        "too_many_positions",
        "too_many_scenarios",
    ],
)
def test_closed_bounded_language(change):
    from settlement_recon.treasury import StressRequest

    data = request_data()
    if change == "duplicate_position":
        data["positions"][1]["id"] = "invoice"
    elif change == "duplicate_scenario":
        data["scenarios"] *= 2
    elif change == "float_shock":
        data["scenarios"][0]["shocks_bps"]["USD"] = 2.5
    elif change == "unknown_field":
        data["sql"] = "SELECT 1"
    elif change == "too_many_positions":
        data["positions"] *= 20
    else:
        data["scenarios"] *= 9
    with pytest.raises(ValidationError):
        StressRequest.model_validate(data)


@pytest.mark.parametrize(
    "change", ["unknown_currency", "reporting_shock", "unknown_shock", "missing_source"]
)
def test_invalid_source_assumptions_fail_closed(change):
    from settlement_recon.treasury import StressRequest, analyze

    data, source = request_data(), snapshot()
    if change == "unknown_currency":
        data["positions"][0]["currency"] = "ZZZ"
    elif change == "reporting_shock":
        data["scenarios"][0]["shocks_bps"]["EUR"] = 1
    elif change == "unknown_shock":
        data["scenarios"][0]["shocks_bps"]["ZZZ"] = 1
    else:
        source = {"status": "not_connected"}
    with pytest.raises(ValueError):
        analyze(source, StressRequest.model_validate(data))
