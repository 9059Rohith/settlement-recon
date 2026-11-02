# FX exposure and deterministic stress lab

[Try the public lab](https://rohith-settlement-recon.vercel.app/workspace/treasury). It uses the actual retained Frankfurter/ECB observation; visitor-authored cash flows are assumptions, not imported financial records. Nothing is persisted or sent to an AI provider. No credentials are required.

## What the engine does

- Net receivables and payables within each currency while preserving gross cash-flow obligations and per-currency concentration.
- Value into any captured reporting currency. ECB quotes are units per EUR, so valuation uses reporting quote divided by cash-flow quote, not the inverse. Decimal-string inputs become exact rational numbers; all valuation, netting, scenario differences and limit comparisons remain rational. Only recurring output values are rounded to50 significant digits using an isolated half-even Decimal context. The UI compact summary explicitly truncates six fractional digits with an ellipsis; export retains full precision.
- Run1–8 independent hypothetical scenarios, each with up to30 explicit currency-value changes in basis points. Reporting currency cannot be shocked against itself. Report each currency's contribution and worst loss among the supplied scenarios, plus breaches of the optional absolute net-value limit.
- Export typed assumptions, source/capture/date digest, input fingerprint and report fingerprint. The report digest is SHA256 of canonical sorted compact ASCII JSON excluding report_digest; hashes identify content and are not digital signatures. Re-running the same assumptions and source produces the same report.

## Safety and bounds

The request language forbids unknown fields, duplicate JSON keys, nonfinite constants, duplicate row/scenario names, executable expressions and arbitrary source URLs. It permits1–50 cash flows, amounts positive and at most1e12 with6fractional digits,1–8 scenarios, and integer shocks from-9000 to9000bps. The32KiB cap is enforced on streamed bytes as well as declared size; deeply nested input returns sanitized422. Cross-site browser requests are rejected. Captured FX source reads are the only database operation. Financial mutation endpoints remain authenticated, and AI quotas are untouched.

The input form is disabled while a request is running, and a revision fence discards a response if its draft changed. Export contains the precise submitted assumptions so it can be independently replayed. Failed requests restore controls. Editing a completed draft invalidates its old report.

## Verification

New tests were run red before implementation. Hand-derived cases verify USD2/EUR and GBP0.5/EUR: receivables70EUR, payables30EUR, net40EUR, gross100EUR, concentration HHI0.68; USD-1000bps/GBP+2000bps yields42EUR and+2EUR. Additional cases cover offsetting large amounts, caller rounding isolation, zero-shock recurring quotes, exact fingerprints, quote direction, invalid currencies and redacted input errors. API tests verify missing-source503, public analysis200, cross-origin403, oversize413, invalid422 and private-ledger401 with the actual database source unchanged.

Final local suite:192passed,6optional PostgreSQL/MinIO skips (recorded separately from earlier integration evidence);4Node formatting/safe-markup cases passed. Existing Starlette/httpx TestClient deprecation warning remains. [Benchmark](../evidence/treasury-benchmark.json):200 repeated pure-engine calls,50 controlled cash flows,8 scenarios,29 real captured quotes; p50 6.36ms/p95 10.12ms/p99 13.69ms. Excludes network, SQL and HTTP, measured on this host; not a production SLA. Workload cash flows are controlled assumptions, not customer transactions.

Reproduce with the project installed, or set PYTHONPATH=src, then run python scripts/evaluate_treasury.py CAPTURE_JSON OUTPUT_JSON.

## Design trade-offs and interview prompts

Why rational numbers? Floating-point valuation and prematurely rounded recurring cross-rates can create false residual risk after offsetting; exact fractions eliminate that class of error under a small bounded workload. Why gross concentration? A fully offset portfolio can have zero net value while still carrying large gross obligations, so a net denominator is misleading. Why no VaR? One reference capture cannot establish a loss distribution, volatility or correlations. Why not execute a hedge? Reference observations are informational and the platform has no banking or brokerage integration. Shocks are independent scenarios, not additive market paths.

## Research

[ECB reference-rate guidance](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html) defines quote direction and the informational boundary. [Python Decimal](https://docs.python.org/3/library/decimal.html) documents precision/rounding controls. [Modern Treasury account reconciliation](https://docs.moderntreasury.com/ledgers/docs/account-reconciliation) explains financial variance; this lab complements reconciliation through assumption analysis, without claiming a vendor integration.

Limitations: no fees, cash-flow maturities, time-series calibration, correlated shocks, liquidity/credit model, automated trading or investment recommendation. Current source data can be dated; observation and capture times are explicit. This feature does not establish any objective portfolio percentile ranking.
