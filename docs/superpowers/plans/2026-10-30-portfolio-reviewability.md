# Portfolio reviewability and engineering depth implementation plan

> **For agentic workers:** Use the parallel-agent workflow for the three independent repositories; execute the reconciliation task natively with test-driven development. Each owner reads its existing code before settling the interface.

**Goal:** Improve the four existing, publicly deployed engineering projects with one defensible operational capability each and evidence-led READMEs.

**Architecture:** Preserve each repository's current Python/SQL boundaries and free Vercel/Neon deployment. New operational capabilities remain authenticated; public pages expose only existing synthetic aggregates. No new cloud services, paid resources or dependencies are required.

**Tech stack:** Existing FastAPI, SQLAlchemy/psycopg, PostgreSQL, SQLite, Parquet/DuckDB, Docker and repository toolchains.

**Spec:** The user's request to improve all four projects and their READMEs; prior authorization to work autonomously, deploy and publish under 9059Rohith remains applicable.

## Global constraints

- Do not claim an independently measured percentile ranking, hiring guarantee, unexecuted benchmark, scheduler or AWS deployment.
- Keep source changes inside the assigned repository. Root coordinates credentials, public releases and publication.
- Never log or commit deployment secrets. Keep public views synthetic-only and private operational routes authenticated.
- Preserve existing dependencies, runtime pins, durable state and public URLs.
- READMEs must distinguish live, locally verified and configuration-only capabilities; link exact evidence and runnable commands.

## Review focus

- Monetary explanation and reconciliation must use one consistent snapshot and the same matching rules.
- Correctness reports must not claim source/projection consistency across different snapshots.
- Dataset comparison must validate published version ownership and bound work before returning records.
- Deployment preview must not execute workloads or expose secret values.
- Documentation must not turn a small benchmark or local integration into a cloud throughput/SLO claim.

## Tasks

### 1. Settlement Recon: authenticated reconciliation explanation

Files: `src/settlement_recon/domain.py`, `src/settlement_recon/api.py`, new focused explanation module/tests if appropriate, `README.md`, architecture/interview/traceability docs.

- [ ] Read current SQL and archive contracts; settle a bounded single-payment/currency explanation interface.
- [ ] Write failing tests for partial/matched/missing/orphan outcomes, batch/checksum lineage, currency isolation, unknown IDs and authorization.
- [ ] Implement evidence from a consistent SQL snapshot without duplicating matching rules or allowing unbounded settlement expansion.
- [ ] Run focused and full tests, Ruff, security checks and actual PostgreSQL/container verification.
- [ ] Rewrite README with problem, live links, five distinguishing engineering points, architecture, quickstart, failure walkthrough, measurements, tradeoffs and reviewer path.

### 2. FluxLake: protected correctness inspection

Owner: dedicated agent; existing `fluxlake/` only.

- [ ] Inspect the projection/source snapshot interfaces and plan a bounded source-to-projection audit with explicit consistency semantics.
- [ ] Write failing correctness/negative/authentication tests; implement and run relevant PostgreSQL/native-runtime checks.
- [ ] Rewrite README around actual CDC semantics, recovery, deployed request synchronization, measured evidence and an executable reviewer walkthrough.

### 3. DataGuard: published-version comparison

Owner: dedicated agent; existing `dataguard/` only.

- [ ] Inspect immutable publication storage; plan an authenticated, bounded comparison of two published versions with provenance.
- [ ] Write failing change/correctness/negative/authentication tests; implement and verify against the real storage backend.
- [ ] Rewrite README around publication invariants, actual failure recovery, contracts, evidence, deployment and a reproducible reviewer walkthrough.

### 4. PipeFoundry: safe deployment change preview

Owner: dedicated agent; existing `pipefoundry/` only.

- [ ] Inspect config/revision/lease interfaces; plan an authenticated preview of create/update/no-op with structured changes and no workload execution.
- [ ] Write failing no-side-effect/diff/validation/privacy tests; implement and verify real PostgreSQL persistence compatibility.
- [ ] Rewrite README around developer workflow, immutable revisions, backfill/rollback, security, measurements and deploy boundaries.

### 5. Integrate, release and publish

- [ ] Review diffs and documentation claims; verify relative links, referenced commands and evidence.
- [ ] Build and scan changed runtime images; deploy all changed backends to their existing free projects.
- [ ] Exercise new authenticated capabilities over actual HTTPS and recheck public summaries/health/privacy/restart invariants.
- [ ] Commit and push each finished repository; verify published heads and live links match the delivered work.
