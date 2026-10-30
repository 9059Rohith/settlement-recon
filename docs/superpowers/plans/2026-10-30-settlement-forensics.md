# Settlement Forensics implementation plan

> For agentic workers: execute natively with test-driven development and verification before completion. Three independent sibling projects are delegated separately.

**Goal:** Add an advisory, ambiguity-aware allocation engine for investigating unmatched synthetic payments, with exact bounded optimization and reproducible evaluation.

**Architecture:** Strict request models define payment claims, unlinked bank legs and an explicit policy. Candidate generation enforces currency, exact integer amounts/tolerance, reference agreement and date windows. A component-wise memoized search maximizes matched payment count, then declared evidence quality; traversing all optimal transitions identifies consensus and ambiguity. Capacity or work exhaustion abstains rather than presenting an incomplete search as optimal. No ingestion or ledger writes occur.

**Tech stack:** Existing Python, Pydantic, FastAPI, pytest; standard-library algorithms, no new runtime dependencies.

**Spec:** User requests substantial executable depth and a distinct project identity for data science and DevOps, with no questions. A fixed code count is a rough scope indicator, not a quality metric. No historical-first or percentile certification is claimed.

## Constraints and review focus

- Maximum24 payments/32legs; split groups1–3; candidate and search budgets; protected body read with size/deadline limits. Currency groups never share legs or monetary sums.
- Scores are deterministic policy preferences, not probabilities. A unique optimum can still be a false business match; recommendations remain advisory.
- All optimal alternatives must be considered before marking a suggestion unique; exhaustion and ambiguous repeated amounts require abstention.
- Request/policy canonical digests support reproducibility. Nothing modifies ledger state or grants new write authority.
- Synthetic evaluation includes indistinguishable decoys so results expose evidence limitations rather than asserting perfect accuracy.

## Tasks

1. Add `tests/test_forensics.py`: run RED for missing engine; assert exact/split matching, ambiguity, capacity, input validation, currency/reference/date isolation, global allocation and permutation invariance. Compare small amount-only problems with an independent exhaustive assignment oracle.
2. Add `forensics_models.py`, `forensics_candidates.py`, `forensics_solver.py`, `forensics.py` with cohesive typed boundaries; run GREEN and full regression.
3. Add protected POST `/v1/forensics/analyze`, CLI `forensics FILE`, and strict input-error sanitization. Test unauthenticated body denial, bounded slow/oversized bodies, reader access, no database effects, typed OpenAPI and CLI.
4. Add deterministic synthetic scenarios and `scripts/evaluate_forensics.py`; record actual precision/coverage/ambiguity and runtime samples against independent known allocations, including decoy limitations.
5. Run full PostgreSQL/MinIO suite and native image tests; audit/scan; update concise README signature and failure/evaluation guidance; commit, deploy and prove authenticated/public boundaries over actual HTTPS.
