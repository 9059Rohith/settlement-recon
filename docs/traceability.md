# OpenFX requirements traceability

| JD requirement | Implementation | Verification |
|---|---|---|
| Python / SQL / relational data | domain service; SQL grouped reconciliation; PostgreSQL tables | test_domain.py, test_postgres.py, test_query_budget.py |
| Multi-source structured / semi-structured ingestion | strict JSON, CSV and bounded partner HTTP | test_domain.py, test_partner.py, HTTP smoke |
| Data quality / duplicates / incremental updates | exact currency rules, immutable receipts, unique keys, quarantine | conflict/replay/partial/orphan/property tests |
| Reliable batch orchestration / Airflow | dated input DAG, safe retries, two ingestion tasks | CI Airflow DagBag job; CLI subprocess replay |
| Monitoring / troubleshooting / recovery | health/readiness, Prometheus exporter, raw verification | API negative/metrics tests; restart and archive-failure tests |
| AWS / Terraform | ECS, ALB TLS, RDS, S3, ECR and task IAM | Terraform format/init/validate evidence; apply blocked without AWS inputs |
| Docker / Linux / networking | non-root image, read-only root, loopback ports, isolated DB network | actual Compose build/health + HTTP smoke; security docs |
| CI/CD / Git / automation | CI gates, OIDC immutable-image deploy and rollback | GitHub workflow runs; AWS release workflow unrun without role/infrastructure |
| Prometheus / Grafana | authenticated exporter, alert rules, dashboard JSON | HTTP exporter tested; independent monitoring-server rollout is optional |
| Documentation / developer productivity | operator CLI, ADRs, recovery and release guide | CLI tests and documented reproduction commands |
| Actual public deployment / durable recovery | Vercel Docker + isolated Neon PostgreSQL; database raw archive; serialized cold-start DDL | live HTTPS readiness/demo; test_database_archive.py, test_schema_startup.py, concurrent PostgreSQL startup test |
| Public exposure / data privacy | synthetic-source SQL scoping, exact Host allowlist, pre-body auth, upload deadline, hashed docs CSP | test_public_demo.py, test_public_security.py; public and private HTTP verification |
| Investigation / documentation / SQL reasoning | typed authenticated explanation, shared rule classifier, full-group lineage checks, read snapshot | test_explanation.py; PostgreSQL concurrent-writer/read-only-reset test; CLI explanation test |
| Reproducible evaluation | generated-ID-scoped reconciliation and one-payment explanation timings | test_evaluation.py; evaluate.py outputs assertion-backed samples |

Spark and Kubernetes are deliberately covered by the other portfolio projects; this service uses SQL and ECS where sufficient. See VERIFICATION.md for the exact boundary between executed checks, SDK unit tests and unexecuted cloud integration.
