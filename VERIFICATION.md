# Executed verification — 2026-10-30

## Public-host hardening and deployment update

- The actual Docker backend is publicly reachable on
  [the live synthetic dashboard](https://rohith-settlement-recon.vercel.app/demo),
  with durable Neon PostgreSQL. This supersedes the earlier absence of a public
  endpoint; AWS remains undeployed.
- **75 tests passed** inside the minimal Python3.15.1 runtime against real
  PostgreSQL and encrypted S3-compatible MinIO, including concurrent empty-schema
  startup, content-addressed database archival, restart, synthetic-source isolation,
  pre-body authorization and slow-upload deadline regressions.
- Fresh Trivy vulnerability + secret scan reports **zero vulnerabilities at all
  severities and zero secrets**, using the database updated2026-10-30 13:06UTC.
  No severity filter, ignore-unfixed flag or vulnerability suppression was used.
  `evidence/public-image-scan.json` retains the actual image identity.
- Ruff passes. Bandit's medium/high gate passes; the intentional container
  listener has one explicit B104 annotation. The optional disabled read-token
  default is a low-severity B107 false positive, not an embedded credential.
- A dedicated non-superuser database role, verified TLS/CA/hostname/channel binding,
  revoked public database access and negative cross-project connection tests were
  applied to the hosted deployment. Public output is synthetic-only; operational
  APIs still require authentication.

Earlier measurements below are dated local evidence, not public-cloud latency
claims. Free-host request measurements are recorded separately.

This is an original, locally verified engineering portfolio system using synthetic data. AWS deployment and remote CI success are separate claims and are not inferred from configuration files.

| Check | Actual result / evidence |
|---|---|
| Full suite with real PostgreSQL 17.9 + encrypted MinIO | **61 passed**, 30.08 s; one upstream Starlette/httpx test-client deprecation warning. `evidence/tests.txt` |
| Coverage | **81%** total, **95%** domain, **85%** API, **92%** S3. CLI subprocess behaviour is tested but subprocess lines are outside this coverage measurement. |
| Correctness | Exact fees/partial/missing/overpaid/orphan results; duplicate/conflict/currency/precision validation; restart/concurrent replay; corrupt archive detection; failed archival has no DB effect. |
| Independent review | Four reproduced material findings corrected: truncated CSV timestamp, non-ASCII auth, SQLite aggregate overflow, inconsistent two-query reads. Additional blank-token and duplicate-JSON-key regressions corrected. Red/green outputs retained. |
| Query budget | Original 200-row ingestion executed **603 SQL statements**. Bulk prefetch/insertion now passes the <=8-statement budget without changing business effects. `tests/test_query_budget.py` |
| SDK/S3 integration boundary | Unit tests verify request parameters/error sanitization with botocore Stubber. A separate test actually writes/reads/replays/verifies encrypted objects against MinIO. This is **S3-compatible integration**, not AWS IAM/TLS verification. |
| Runtime dependencies | Exact installed 29-package closure audited: **zero known vulnerabilities**. `evidence/dependency-audit.json`; resolution warnings recommend hash-pinning. |
| Static checks | Ruff check/format, Bandit medium/high gate, compile checks executed. See retained outputs for final rerun. |
| Secret scan | Trivy filesystem secret scan: **0 detected secrets**; `.env`, runtime data, virtualenv and `.git` excluded. `evidence/secret-scan.json` |
| Terraform | Real AWS provider v6.71.0: init and validate succeeded; fmt passed. Provider archive verified against official SHA256SUMS; cross-platform hashes retained. `evidence/terraform-validate.txt` |
| Infrastructure security | Trivy reports no unsuppressed HIGH/CRITICAL findings after private endpoints/egress, KMS and invalid-header hardening. Intentional public HTTPS ALB rule exception is annotated with its reason. `evidence/iac-scan.json` |
| Actual Docker/HTTP | Non-root image built and Compose API/PostgreSQL started. Actual HTTP smoke passed readiness/docs, denied auth/non-ASCII auth, upload/replay, exact fee matching, quarantine, archive verification and metrics. `evidence/http-smoke.json` |
| Actual partner HTTP | A real local synthetic partner API served authenticated data; the bounded connector wrote to PostgreSQL and replayed without duplicate effects. `evidence/partner-http-smoke.json` |
| Container vulnerability check | **0 fixable HIGH/CRITICAL** findings against cached vulnerability DB updated **2026-10-20**. Runtime Python dependency audit above is separately current. `evidence/container-scan.json` |
| Actual Airflow import | **Airflow 3.1.0** Linux container DagBag import passed, with `reconciliation` and two dependent tasks. This is an older-runtime compatibility check; configured Airflow3.3.2 CI remains blocked. `evidence/airflow-compatibility.txt` |

## Benchmark method

`scripts/evaluate.py` inserts 1,000 synthetic payments and settlements, asserts exact matching, times 30 warm reconciliation queries/replays, quarantines corrupt input, disposes/reopens the engine and asserts replay returns the original batch. It records environment, UTC timestamp and percentile method. PostgreSQL tests traverse Windows-to-Docker TCP. Other builds were active. These are small local samples, not production SLOs, saturation tests or cloud latency measurements.

`evidence/benchmark-before.json` captures the earlier per-row implementation; final benchmark files are regenerated after the single-statement snapshot and cumulative-bound fixes. Query-budget reduction is a deterministic regression result; single-run timing differences are not a statistically established speedup claim.

## External blockers and remaining limits

- No matching AWS credentials, deployment role, token-secret ARN, issued ACM certificate/DNS or Terraform backend were available. **No AWS apply is claimed.** The free public alternative is documented above.
- GitHub workflows can be published using the signed-in account; an account-level runner restriction prevents remote Actions jobs from starting. Local tests are the executed verification evidence.
- No live Airflow scheduler or AWS ECS rollback drill is claimed. Actual older-runtime DAG import is verified above. A pinned current Airflow DAG-import CI job is included; blocked runners do not count as an executed job.
- This implementation has shared operator tokens, serialized writers, a bounded reconciliation response and initial owner-role schema creation. It does not establish regulated-production readiness, complete accounting coverage, perfect security or unlimited scalability.

The verified local application is available at http://localhost:8011, API console `/docs`, health `/healthz`, readiness `/readyz`. These are local URLs, not public cloud deployments. Final PostgreSQL 1,000-row reconciliation microbenchmark: p50 **99.503 ms**, p95 **164.756 ms**, p99 **216.711 ms**, 30 warm samples; complete raw report and method are in `evidence/benchmark-postgres.json`.

Final input-budget regressions also verify that deeply nested JSON is quarantined and CSV iteration stops at the row limit. Container concurrency is capped at eight for the bounded batch service; it is not a throughput guarantee.
