# Settlement Recon Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. User explicitly requests autonomous execution and no questions.

**Goal:** Reconcile synthetic payments and settlement statements with auditable, safe replay and deployable infrastructure.

**Architecture:** FastAPI and CLI call a shared domain service. PostgreSQL stores immutable business records, batches and exceptions; raw artifacts use a content-addressed filesystem or S3 adapter. Airflow invokes the same ingestion boundary. Monetary arithmetic uses exact minor units and SQL aggregation.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, PostgreSQL, Airflow, S3, Docker, Terraform AWS ECS, GitHub Actions, Prometheus/Grafana.

**Spec:** User's four-project execution request and both supplied OpenFX internship PDFs.

## Global Constraints
- Independent repository; only synthetic example data; no claimed deployment without verification.
- Fail closed when API_TOKEN is absent; authenticated data and mutation APIs; bounded input sizes.
- PostgreSQL production, SQLite portable local evaluation explicitly labelled.
- Exactly-once business effects through constraints and serialized ingestion, not transport guarantees.

## Review Focus
- Same id with changed amount must quarantine, not overwrite.
- Partial settlements across statements must sum correctly with fees.
- Concurrent ingestion of identical input must have one business effect.
- Archive outage must not commit database effects; corrupt archives must fail verification.
- Invalid CSV/JSON, timestamps, precision and unrecognised currencies must fail safely.

## Tasks
1. [x] `tests/test_domain.py`, `src/settlement_recon/domain.py`: tests first for currency parsing, CSV/JSON, duplicate/conflict/partial/orphan/fee and reruns; watch red then implement.
2. [x] `tests/test_api.py`, `api.py`, `cli.py`: auth, bounded requests, health, metrics, negative routes, real CLI and simulated partner pull. Red then green.
3. [x] `tests/test_recovery.py`, `scripts/evaluate.py`: concurrency, archive failure, restart replay and measured benchmarks. Red then green.
4. [x] Docker, Airflow DAG, Terraform ECS/RDS/S3/IAM/TLS, CI/CD, monitoring: validate available tools and clearly record external blockers.
5. [x] README, architecture, ADRs, security, runbooks, interview, traceability: match actual code and evidence; final full suite, lint, dependency audit and fresh code review before publication.

## Execution ledger
- 2026-10-30: Starting independent repository; no existing application code. Local Docker startup under investigation. Cloud credentials not yet available. Local Git credentials match target GitHub owner.

- Implementation complete: 61 tests including PostgreSQL and encrypted MinIO passed; independent review findings fixed with retained red/green regression evidence.
- Performance: bulk prefetch eliminated per-row SQL; final microbenchmarks retain exact environment and timing scope.
- Deployment: local Docker/HTTP and actual older Airflow import verified. Terraform private networking/KMS/least-privilege configuration validated and scanned. AWS apply blocked by absent account credentials/inputs.
- Publication: source and workflow upload use matching 9059Rohith account; hosted runners blocked by account-level restriction. No hosted CI or AWS success claimed.
- Plan adjustment: recovery tests live in test_domain.py/test_archive.py/test_review_regressions.py rather than a separate test_recovery.py; this keeps tests beside the invariants they exercise.
