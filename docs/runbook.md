# Operation, deployment and recovery

## Local flow

Generate `.env`, build/start Compose, then run `docker compose exec api settlement-recon demo`. It ingests two payments and a statement, quarantines malformed input and replays the original statement. `matched=1`, `partial=1`, one quarantine are assertions in the automated CLI test, not a hardcoded API response.

The API's `/docs` is the operator UI. Use Authorize and paste the local writer token. Upload `examples/payments.json` to the payments route and `examples/statement.csv` to the statement route with distinct sources. Inspect the receipt, reconciliation and archive verification endpoints.

`docker compose down` stops the project but preserves data volumes. Back up data before using `down -v`; that command deletes local project data. Never run a global Docker prune.

## Quarantine and replay

1. Find the batch through `/v1/batches`; note its source, checksum and validation code.
2. Verify the raw object through `/v1/batches/{id}/verify`. A false result is an archive integrity incident; restore original bytes from trusted backup/version history before proceeding.
3. Correct the upstream file rather than changing stored payment rows. Reingest corrected bytes under the same source to create a new batch.
4. Conflicting existing identifiers need an upstream investigation. The service intentionally has no unaudited overwrite endpoint.
5. Retry after a database/archive outage. Uncommitted database rows roll back; identical input has one business effect after recovery.

## Scheduled batches and backfills

The Airflow3 DAG reads `<RECON_INPUT_ROOT>/<ds>/payments.json` and `statement.csv`; dates come from the scheduled data interval. Set `RECON_API_URL` to a trusted HTTPS origin and inject `RECON_API_TOKEN` from your Airflow secret backend. Install the package's `httpx` dependency in the Airflow environment. Store files on a shared mounted input volume, not a worker's ephemeral filesystem.

Import-check: `python -c "from airflow.models import DagBag; b=DagBag('dags',include_examples=False); assert not b.import_errors,b.import_errors"`. CI runs this in a pinned Airflow environment. Backfill using Airflow's UI for the specific data interval after placing immutable files in its dated directory. Resetting an identical accepted task is safe; quarantined content must first be corrected. The API transaction is atomic per batch, not across both DAG tasks.

## Partner API demonstration

Set a >=32-character `PARTNER_TOKEN`, run `uvicorn examples.partner_api:app --port 9901`, set `PARTNER_ALLOWED_HOSTS=127.0.0.1`, then run `settlement-recon pull-partner http://127.0.0.1:9901/payments`. The connector authenticates, bounds downloads and retries transient errors only. The simulator is explicitly synthetic.

## AWS prerequisites and release

Required external inputs: an AWS account/region with deployment permissions; an issued ACM certificate for an owned DNS name; an existing Secrets Manager token secret; and protected Terraform state storage. No AWS account is embedded or inferred from unrelated connected services.

1. Configure an AWS CLI/SDK profile. Run Terraform init/validate, then plan with `region`, `image`, `api_secret_arn`, `certificate_arn`. Review the plan and regional pricing before apply. ALB/RDS/Fargate are billed while running.
2. Initial bootstrap can use `desired_count=0` and the intended ECR commit image URI. Apply creates ECR/infrastructure without starting an unfetched image. Build/push that image, then apply `desired_count=1`.
3. Point the certificate's DNS name to the ALB. Verify HTTPS readiness and authenticated ingest/reconcile/archive verification through that name.
4. Configure the repository's `production` environment with `AWS_ROLE_ARN`, `ECR_REPOSITORY`, `ECS_CLUSTER`, `ECS_SERVICE`, `PUBLIC_URL`. Bind the AWS OIDC trust to exactly `repo:9059Rohith/settlement-recon:environment:production` and audience `sts.amazonaws.com`.
5. The deploy workflow builds a commit-tagged image, registers a new task revision, waits for stability and checks HTTPS readiness. It detects ECS circuit-breaker rollback and reverts to the prior revision on failure. Terraform owns infrastructure; use its image variable consistently after a release to avoid accidental rollback.

Restrict deployment IAM to this ECR repository, ECS service/task family and the two task IAM roles (`iam:PassRole` for ECS only). Deployment must not use an administrator key. Terraform needs broader provisioning privileges and is intentionally not auto-applied on pull requests.

## Monitoring and incident triage

Scrape `/metrics` using a private read token over a trusted network/TLS. Alert on persistent 5xx responses, ingestion quarantine growth and p95 request latency. Counters reset on process restart; receipt history is the durable source of ingestion outcomes. The checked-in dashboard queries these real metrics. Cloud/platform metrics should also cover ALB healthy hosts, ECS task restarts, RDS connections/storage and S3 errors.

For database failures: check `/readyz`, task logs, RDS health, security-group paths and DNS resolution from the task subnet. For S3 failures: check task role/prefix permissions and endpoint connectivity. For lock timeouts: inspect long transactions; retry immutable input after fixing the cause. Never log full credentials during diagnosis.

Tasks in the AWS profile run in private subnets without public addresses; ECR/Logs/Secrets Manager use interface endpoints and S3 uses a gateway endpoint. Regional endpoint charges apply. The third-party partner connector needs a separately approved outbound proxy/connector; default AWS tasks cannot make arbitrary Internet calls. AWS apply remains blocked until account-specific inputs exist. The actual free Vercel/Neon public deployment is described in [the hosted profile](public-deployment.md); local PostgreSQL/Docker verification is recorded separately.

## Investigate a reconciliation exception

Run `settlement-recon explain demo-partial INR --limit 5` against the CLI demo database, or the same command through `docker compose exec api` for PostgreSQL. The HTTP equivalent is `GET /v1/reconciliation/demo-partial/INR/explanation?limit=5` with a writer or reader bearer token.

Read `rule`, exact `totals` and `settlements.total_rows` first. If `truncated=true`, the returned bank legs are a sample, while totals still cover every matching leg. Inspect payment/settlement batch IDs and checksums, then use `verify <batch_id>` or its authenticated HTTP route to re-read raw bytes. Do not treat `archive_integrity_checked=false` as a successful integrity check.

Broken receipt references return503 rather than fabricated lineage. Investigate the protected database and retained raw archive; do not edit accepted inputs or reuse an existing business ID for conflicting values. A missing group returns404 and is distinct from a known payment with no settlement (`status=missing`).
