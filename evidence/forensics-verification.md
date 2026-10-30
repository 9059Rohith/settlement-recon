# Settlement Forensics verification

Executed on2026-10-30. This revision adds executable allocation investigations, SQL case extraction, protected HTTP, a standalone CLI and controlled synthetic evaluation. It does not establish a percentile ranking or production matching accuracy.

- Observed RED:19 missing-engine cases,6 API/CLI cases,6 SQL-extraction cases, and the complete-reference-policy regression. All targeted tests subsequently passed.
- Independent oracle:40 seeded small amount-only problems compare decision ambiguity with exhaustive allocations, separately from the production solver.
- Controlled study:40 trials of each of8 designed scenarios, evaluated under two policies. Default precision90.91%, coverage68.75%,40 false suggestions. Complete-reference precision100%, coverage50%,0 false suggestions. Decoys and ambiguous collisions remain in the denominator; labels never enter the engine. Raw records/method: `forensics-evaluation.json`.
- First native full regression:134 passed and1 failed. Actual PostgreSQL returned `Decimal('10000')` from SUM(bigint), unlike SQLite's int; strict output validation rejected it. Actual TCP case extraction reproduced the same failure. Integral SQL aggregates are now explicitly converted at the boundary; the PostgreSQL snapshot regression is retained. Final rerun results are recorded separately, never inferred from the initial failure.
- Root request controls authenticate before body consumption;128KB, five-second read deadline, depth/duplicate-key checks, sanitized errors and two compute slots. Tests exercise actual slow/unread bodies, capacity, typed OpenAPI, no ledger mutations, global competing allocations, candidate/search limits and count capping.

Final verification after the aggregate-boundary fix:

- Full Windows Python3.12 suite with real PostgreSQL/MinIO: **135 passed**,150.77s.
- Full actual minimal Python3.15.1 runtime with real PostgreSQL/MinIO: **135 passed, no skips**,90.54s; one upstream Starlette/httpx deprecation warning. Complete output: `public-runtime-tests.txt`.
- Actual installed-image TCP HTTP: payment+orphan-bank ingestion → SQL case extraction → advisory analysis → ledger remains unmatched. `forensics-native-http.json` records UID10001/read-only root and actual image identity.
- Fresh all-severity runtime vulnerability+secret scan: **zero known vulnerabilities and zero detected secrets**, `signature-image-scan.json`; no severity filters/suppression.
- Independent review found no material issue and compared100 additional seeded split/tolerance/currency cases with an exhaustive oracle:100/100 decision/objective agreements.
- Ruff lint/format and Bandit medium/high gate pass; the earlier documented optional-token low static finding remains separately scoped.

Historical verification artifacts elsewhere retain their original scope; no hosted Actions success or AWS apply is claimed.
