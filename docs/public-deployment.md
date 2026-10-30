# Public deployment

The free portfolio deployment runs the actual Docker API on Vercel Hobby with
durable PostgreSQL on Neon Free. It processes synthetic records only.

- [Live reconciliation dashboard](https://rohith-settlement-recon.vercel.app/demo)
- [Actual JSON evidence](https://rohith-settlement-recon.vercel.app/demo/summary)
- [Interactive API documentation](https://rohith-settlement-recon.vercel.app/docs)
- [Liveness](https://rohith-settlement-recon.vercel.app/healthz) and
  [database/archive readiness](https://rohith-settlement-recon.vercel.app/readyz)

## State and trust boundaries

`RAW_STORE=database` stores original input bytes in a content-addressed PostgreSQL
table, outside the ingestion transaction. Conflicting bytes for an existing digest
are rejected, and reads verify SHA256. Original accepted and quarantined inputs
survive container replacement. This is integrity-checked storage, not a defence
against a compromised database owner. The encrypted S3 adapter remains appropriate
for larger archives and separate IAM permissions.

The three fixed synthetic payments, two bank rows and invalid batch are seeded
through the real ingestion engine. Repeated startup returns existing receipts.
Public aggregation restricts SQL to the reserved fixture IDs and synthetic source
before applying query limits. Other payment records and bank sources are excluded.
Raw inputs, ingestion, batch receipts and metrics require strong operator tokens.

Each project has a separate database and a non-superuser role. The deployed
connection requires hostname-verified TLS with the container's CA bundle and TLS
channel binding. Cross-project database CONNECT was tested and denied. The hosted
roles have a 15-second statement timeout, 10-second lock timeout and 30-second idle
transaction timeout. Credentials exist only in encrypted server environment
variables and ignored local deployment configuration.

Both archive and domain schema bootstrap serialize DDL using a PostgreSQL
transaction advisory lock (SQLite uses BEGIN IMMEDIATE). Concurrent cold startup
is tested. The database adapter does not require local writable archival storage.
The public host allows only its named domain and health-check loopback hosts.

## Runtime and recovery

The release image uses digest-pinned minimal Chainguard Python3.15.1, UID10001,
locked dependencies and no shell/package manager/installer. Inputs have schema,
byte, row and identifier limits. Unauthorized uploads are rejected before body
consumption; authenticated uploads have a ten-second read deadline. Documentation
uses explicit bootstrap script hashes and a narrow asset CSP.

Vercel's container runtime is Beta and scales to zero. A first request can take
longer while the service or database wakes. The filesystem is disposable; the
database and raw archive are authoritative. Free plan quotas are shared with
other account projects and do not constitute an availability SLA. No AWS resource
was provisioned, and a live Airflow scheduler is not part of this free deployment.

## Reproduce

Create an isolated PostgreSQL database and a restricted login role. Configure
server-only `DATABASE_URL`, `API_TOKEN` (at least 32 characters), `RAW_STORE=database`,
`PUBLIC_DEMO=true`, `SEED_DEMO=true`, `DATA_DIR=/tmp/recon`, `PORT=8000` and the
exact public domain in `ALLOWED_HOSTS`. Deploy the root Dockerfile using Vercel's
Container preset. Keep preview deployments protected and production public.
Never publish API tokens in the page, source code or frontend environment.

Use a previous verified deployment for application rollback; retained SQL records
and content-addressed archives remain in PostgreSQL. Data migrations require a
separate compatibility review; application rollback does not undo database data.

## Verify the actual runtime

Build `docker build -t settlement-recon:public .`, then
`docker build -f scripts/Dockerfile.runtime-tests -t settlement-recon:runtime-tests .`.
Run the latter image with the checkout mounted read-only at `/work`, a writable
tmpfs at `/tmp`, and `HYPOTHESIS_STORAGE_DIRECTORY=/tmp/hypothesis`. Supply
`TEST_DATABASE_URL` and the S3 test variables from `tests/test_s3_integration.py`
through an ignored environment file to execute integration cases. Without these
variables the suite explicitly skips those integrations. On Docker Desktop the
host services are reachable through `host.docker.internal`; no public secret is
required or embedded in the image.
