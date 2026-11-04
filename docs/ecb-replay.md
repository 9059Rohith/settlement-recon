# Historical FX replay

[Live historical replay](https://rohith-settlement-recon.vercel.app/workspace/history)

The replay uses the European Central Bank's original `eurofxref-hist.csv` ZIP, retrieved on 4 November 2026. **Source: ECB statistics.** The original ZIP is stored byte for byte in `src/settlement_recon/assets/ecb-historical.zip`. SHA-256: `c790546ee569ee4461356cc36b76e312d8f3ca0a4ff9990094ecaeb8f3de5f0c`. It contains 7,128 publication dates from 1999-01-04 through 2026-11-03. [Official archive](https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip) · [ECB reuse policy](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html).

Choose a pair and a window of up to 366 calendar days. The service divides target units per EUR by source units per EUR with exact rational arithmetic. JSON evidence gives both published quotes, the exact fraction, and a deterministic report fingerprint. Changes are derived from successive available observations. Weekends, unavailable currencies and other gaps are not filled. These are reference rates, not customer payment records or executable prices.

The [benchmark](../evidence/ecb-history-benchmark.json) ran 214 pair/year windows covering eight pairs. An independent CSV parse checked the date set and both source quotes; exact cross-products matched for all **54,464** pair observations. Median replay time was **14.06 ms** and p95 **18.50 ms**. Median full archive parse was **213.79 ms** over five trials. These are local in-process timings; download, network and verification oracle are excluded. Windows 11, Python 3.12.0. One pair can have fewer dates because the ECB did not publish both currencies on every date.

Reproduce from the checked-in archive after installing project dependencies:

```powershell
python scripts/benchmark_ecb_history.py --output evidence/ecb-history-benchmark.json
python -m pytest tests/test_history.py tests/test_workspace.py -q
```
