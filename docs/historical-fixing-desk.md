# Historical fixing desk

[Open the desk](https://rohith-settlement-recon.vercel.app/workspace/history#fixing-title)

Enter dated amounts and an explicit reporting currency, decimal precision and
maximum quote age. The service selects the most recent actual paired ECB quote
on or before each record date. It never looks ahead, invents a weekend quote or
fills a missing currency. An over-age quote remains visible as stale but is not
used in a total. Identity conversions need no external quote.

This is calendar-date, end-of-day analysis. It does not establish whether that
day's quote had been published at a particular intraday payment timestamp; no
intraday availability or execution-timing claim is made.

Amounts are visitor-authored inputs, not claimed customer payment records.
Reference rates are informational, not bank settlement evidence or executable
prices. The original ECB archive is pinned byte-for-byte and ends on
**3 November 2026**. Its source URL, dates, ZIP/CSV checksums, exact quote inputs
and report fingerprint accompany every result. A report hash identifies content;
it is not a digital signature or proof of source authenticity.

## Accounting behavior

- Monetary multiplication and cross-rates use exact rational arithmetic.
- Half-even rounding uses integer division, including exact ties.
- The desk separately reports the sum of individually rounded rows, rounded exact
  subtotal and their difference. It does not silently reconcile that difference.
- Any unavailable/stale row makes `complete_total` null. A labeled valued
  subtotal remains inspectable, including when every row is blocked.
- Precision is an explicit reporting policy, not an automatic ISO/legal currency
  rule. Quote age uses calendar days, not a holiday calendar.
- Editing inputs clears the visible evidence and export. An in-flight response
  for an older form revision cannot overwrite the current state.

## API and operating boundary

`POST /workspace/api/fixing` accepts `target_currency`, `rounding_places` (0-6),
`max_quote_age_days` (0-10), and 1-50 uniquely identified `records` with ISO
`date`, `currency` and positive decimal-string `amount` (at most one trillion).
Bodies are limited to 32 KiB, reject duplicate JSON keys and unexpected fields,
and apply the existing same-origin policy. No operator token is required because
the operation reads the fixed public archive and neither accesses private
ledgers nor performs writes, remote requests or model inference. Normal operator
authentication and AI quotas are unchanged.

## Verification

Sixteen new Python cases passed after their missing-feature failures were
observed. The full default profile passed **246 tests, with six explicit optional
PostgreSQL/S3 skips**. Existing five Node UI-format tests, JS syntax, Ruff
lint/format and the medium/high Bandit gate passed. A pre-existing Starlette
httpx deprecation warning remains; no zero-warning claim is made.

The real-archive benchmark independently parsed the original CSV and checked
4,000 analytical one-unit conversions across 80 batches of 50 against Decimal
precision-80 half-even quantization. It observed **1.4901 ms median / 1.9281 ms
p95 per batch** locally. This excludes archive load, HTTP, network and oracle
checks. These are measured analytical conversions, not customer payments or a
hosted latency claim. [Benchmark evidence](../evidence/fixing-benchmark.json)

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe scripts/benchmark_fixing.py
.venv/Scripts/python.exe -m pytest tests/test_fixing.py -q
```

Real Chromium runs at 1440x1000 and 390x844 exercised row entry, a prior-Friday
quote for a Sunday record, actual JSON download/readback, invalidation on policy
edit and a stale-policy result with no complete total. Both had no page runtime
errors or horizontal viewport overflow. The test used a clearly QA-authored
100-unit amount against actual archived quotes. Hosted release observations are
recorded separately from these local checks.
