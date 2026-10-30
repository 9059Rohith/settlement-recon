"""Evaluation includes an unidentifiable decoy and reports it as a false suggestion."""


def test_synthetic_evaluation_reports_real_precision_coverage_and_decoy_limit():
    from settlement_recon.forensics_evaluation import evaluate

    first = evaluate(trials=3, seed=10)
    assert first["scenario_count"] == 24
    ordinary = first["policies"]["default"]
    strict = first["policies"]["complete_reference"]
    assert ordinary["false_suggestions"] == 3
    assert strict["false_suggestions"] == 0
    assert strict["coverage"] < ordinary["coverage"]
    assert ordinary["by_scenario"]["indistinguishable_decoy"]["precision"] == 0.0
    assert ordinary["by_scenario"]["amount_collision"]["ambiguous_payments"] == 6
    assert first["scenario_sha256"] == evaluate(trials=3, seed=10)["scenario_sha256"]
    assert first["scenario_sha256"] != evaluate(trials=3, seed=11)["scenario_sha256"]


def test_scenarios_do_not_change_ledger_or_train_on_test_labels():
    from settlement_recon.forensics_evaluation import scenarios
    from settlement_recon.forensics_models import ForensicsRequest

    rows = list(scenarios(42))
    assert len(rows) == 8
    for row in rows:
        request = ForensicsRequest.model_validate(row.request)
        assert len(request.payments) <= 24 and len(request.legs) <= 32
        assert "truth" not in row.request
