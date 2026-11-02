# FX Exposure Stress Lab Implementation Plan

> For agentic workers: execute test-first inline using executing-plans. User has opted out of design questions and explicitly authorized implementation and publication.

Goal: expose a bounded read-only treasury analysis workflow using actual captured ECB rates and visitor-authored cash-flow assumptions.
Architecture: strict Pydantic input, a separate Decimal engine, existing latest-observation accessor, same-origin public POST, server-built deterministic report with source/request/report fingerprints. No positions are stored or sent to AI. Existing financial mutations and Gemini quotas unchanged.
Tech Stack: existing Python/FastAPI/Decimal and vanilla JS/SVG/CSS, no new runtime dependency.
Spec: this document is the short design and plan.

Global constraints: 1–50 cash-flow rows, 1–8 scenarios, at most30 currency shocks/scenario, amount decimal strings up to1e12 and6fractional digits; basis-point shocks -9000..9000. Reporting currency cannot itself be shocked. Duplicate row IDs and scenario names rejected. No input SQL/code/URLs. Fifty-digit local Decimal precision. Output decimals remain strings. Source timestamp/digest travels with every result. Hypothetical scenarios are not forecasts or VaR.

Review focus: inverse FX quote direction; offsetting receivables/payables; nonfinite/exponent and rounding; unknown currency/reporting-currency shocks; deterministic replay and no source writes.

Alternatives: historical VaR is inappropriate with one dated capture; expanding the converter alone would add little engineering depth. Chosen multi-currency gross/net analysis, deterministic shocks, concentration and limit breaches reveals risk without inventing history.

- [x] Task1 tests/test_treasury.py: hand-derived gross/net and inverse quotes, offsets, scenario deltas, concentration denominator, precision, strict input boundaries, report fingerprint. Run red then implement src/settlement_recon/treasury.py and run green.
- [x] Task2 tests/test_treasury_api.py: no-source503, real captured-source analysis200, no table mutation, same-origin rejection, invalid422/private401. Add existing-workspace endpoint and13th page; run full suite.
- [x] Task3 existing workspace_ui.py/workspace.js/workspace.css: interactive cash-flow rows, scenarios/shock editor, source date, net-exposure chart/table, exact scenario deltas/limit breaches, downloadable report. Empty state until user provides assumptions. No operational fake defaults.
- [x] Task4 bounded benchmark, Ruff/Bandit/JSchecks, review diff, deploy existing freeVercel project, verifypublic endpoint/assets/browserdesktop390/mobileform/result/download. Commit/push evidence and limitations.

References: https://docs.moderntreasury.com/ledgers/docs/account-reconciliation (business variance); https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html (rates informational, not transactions). These sources inform scope; the stress engine is our own implementation, not a vendor integration.

Ruling: exact Fraction valuation from decimal inputs replaces early-rounded Decimal cross-rates, eliminating zero-shock recurring-quote residuals. Output alone uses50digitHalfEven. Independentreviewcaughtstale-responseandduplicateJSONkeys;bothfixedwithinputsnapshot/revisionguard/strictparser.
