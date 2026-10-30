# Settlement Recon

[![CI](https://github.com/9059Rohith/settlement-recon/actions/workflows/ci.yml/badge.svg)](https://github.com/9059Rohith/settlement-recon/actions/workflows/ci.yml)

An auditable reconciliation service for **synthetic** cross-border payment and bank-settlement data. It ingests JSON and CSV, archives original inputs, applies exact monetary rules, identifies exceptions and safely replays failed inputs. It does not connect to a bank or move money.

## What works

- PostgreSQL ingestion transactions serialized across processes with an advisory lock; unique batch and business keys make retries idempotent.
- Exact minor-unit arithmetic for USD/EUR/GBP/INR/JPY; partial settlements, fees, missing payments, overpayments, orphan records and currency boundaries.
- Content-addressed raw archival. Files are flushed before atomic publication; the S3 adapter uses conditional writes, checksums and encrypted objects.
- Entire conflicting or invalid batches are quarantined without partial business effects. Corrected files produce new batches; all original evidence remains queryable.
- FastAPI/OpenAPI console, read/write bearer roles, bounded HTTP ingestion, readiness, bounded partner HTTP retries and authenticated Prometheus metrics.
- Reusable CLI and Airflow 3 daily DAG using data-interval inputs, Docker Compose, AWS ECS/RDS/S3 Terraform and OIDC release workflow with rollback.

## Start locally

Python 3.12+ and Docker Compose are required for the PostgreSQL environment.

```bash
python -m venv .venv
# Activate .venv (Windows: .venv\Scripts\Activate.ps1)
pip install -r requirements-dev.txt
pip install --no-deps -e .
python scripts/setup_env.py
docker compose up -d --build
```

API console: **http://localhost:8011/docs**. Health: `/healthz`; database readiness: `/readyz`. The console's Authorize button takes the `API_TOKEN` from the locally generated `.env`. Never commit that file. Compose publishes PostgreSQL only on `127.0.0.1:55432`.

Run the actual demonstration against the container's PostgreSQL:

```bash
docker compose exec api settlement-recon demo
docker compose exec api settlement-recon reconcile
docker compose exec api settlement-recon batches
docker compose exec api settlement-recon ingest payments example-ledger /path/to/file.json
```

For a portable evaluation without Docker, run `settlement-recon demo` in the activated environment. This explicitly uses SQLite + filesystem under `data/`; it is not an AWS deployment. Input fixtures are in `examples/`. To use them in a container, copy them with `docker compose cp examples/payments.json api:/tmp/payments.json`.

## API

All `/v1/*` routes and `/metrics` require a bearer token. Optional `READ_TOKEN` can read but cannot ingest. Without a >=32-character writer token, data endpoints fail closed with 503. JSON/CSV uploads are limited to 2 MB and 10,000 rows. A successful HTTP request can return a quarantined batch: inspect its `status`, not only HTTP 200.

| Method | Route | Result |
|---|---|---|
| POST | `/v1/ingest/payments?source=ledger` | JSON `{ "payments": [...] }` batch receipt |
| POST | `/v1/ingest/statement?source=bank` | CSV batch receipt |
| GET | `/v1/reconciliation` | Exact amounts, differences and exception status |
| GET | `/v1/batches` | Latest 100 receipts and quarantine errors |
| GET | `/v1/batches/{id}/verify` | SHA-256 archive verification |
| GET | `/metrics` | HTTP latency, request and ingestion counters |

Reconciliation currently returns at most 10,000 combined expected/orphan groups from one consistent SQL statement snapshot. Use offline SQL for larger evaluation; pagination is a documented limitation. Supported monetary values are nonnegative decimal strings with currency-specific precision, bounded to 10^15 minor units. Cumulative settlements including fees are bounded to 10^15 minor units per payment/currency group, across all sources, to keep exact arithmetic portable. IDs are globally unique for payments and unique per bank source for settlement rows.

## Verification and operation

```bash
pytest --cov=settlement_recon --cov-report=term-missing
ruff check .
ruff format --check .
bandit -r src -ll
pip-audit -r requirements.txt
python scripts/evaluate.py --rows 1000
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
```

Set `TEST_DATABASE_URL` to a dedicated PostgreSQL database to execute the real concurrency integration test; otherwise it is explicitly skipped. `evidence/` contains actual results and benchmark methodology. Rerun benchmarks on your hardware; they are not service guarantees.

- [Architecture and decisions](docs/architecture.md)
- [Security model](SECURITY.md)
- [Deployment, recovery and Airflow runbook](docs/runbook.md)
- [JD requirements and verification evidence](docs/traceability.md)
- [Technical interview guide](docs/interview.md)
- [Current verification and deployment status](VERIFICATION.md)

## Deployment status

AWS configuration provisions VPC/subnets, private encrypted RDS, a private versioned S3 bucket, ECR, ECS Fargate, scoped IAM, TLS ALB and automatic deployment rollback. It requires AWS credentials, a token secret and an issued ACM certificate; see the runbook. A checked-in Terraform file is not evidence of a running AWS service. Current status is recorded in `VERIFICATION.md`.

## Design references

Original implementation informed by [Airflow rerun guidance](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html), [AWS event-driven ELT patterns](https://github.com/aws-samples/sample-mwaa-elt-ingestion-glue-rds), and [S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html). No reference repository is presented as the author's own work. MIT licensed.
