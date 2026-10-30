# Architecture and technical decisions

```mermaid
flowchart LR
  JSON[Payment JSON] --> API[Authenticated FastAPI / CLI]
  CSV[Bank CSV] --> API
  HTTP[Allowlisted partner HTTP] --> API
  Airflow[Airflow daily partition] --> API
  API --> Archive[SHA-256 raw archive: database, filesystem or S3]
  Archive --> Parse[Strict parsing + minor units]
  Parse --> Tx[Serialized database transaction]
  Tx --> Batch[Batch receipt / quarantine]
  Tx --> PG[(PostgreSQL payment / settlement tables)]
  PG --> SQL[SQL grouped reconciliation]
  SQL --> Exceptions[Matched / partial / missing / overpaid / orphan]
  API --> Prom[Authenticated Prometheus exporter]
```

## ADR-001: exact arithmetic and explicit currency boundaries

Amounts enter as strings and are converted to integer minor units using Decimal. Net settlement plus fee is compared to the original payment amount. This models a fee withheld from payment proceeds; a different partner accounting convention needs an explicit adapter. No FX conversion is guessed. EUR settlement for a USD payment is an orphan group and the USD payment remains missing. Refunds/negative adjustments require a future explicit record type and are rejected today.

## ADR-002: preserve input before changing business state

The raw archive must acknowledge a complete object before a database transaction begins. The receipt and all new business rows then commit together. A crash between archival and commit can leave an unreferenced object; retry reuses its checksum. This sacrifices perfect cross-store atomicity in favour of recoverable evidence. Missing/corrupt archived bytes fail verification; they are never silently overwritten.

The filesystem adapter writes a private temporary file, flushes it, then links it atomically into the content-addressed namespace. POSIX also flushes the directory; Windows filesystem durability semantics differ. S3 uses `If-None-Match: *`; a 412 requires verifying the existing content.

The free public deployment uses `DatabaseArchive`: a separately committed, content-addressed raw table in the same durable PostgreSQL database. An insert conflict requires byte equality; reads recheck SHA256. Container-local files are disposable. This preserves recoverable inputs without assuming a free host offers a durable filesystem; large archives should retain the separate S3/IAM boundary.

## ADR-003: serialize writers, keep correctness simple

PostgreSQL advisory transaction lock 508172 serializes all writers. SQLite uses BEGIN IMMEDIATE. Constraints provide additional uniqueness protection. This avoids cross-worker races during duplicate/conflict validation. It limits write throughput; the benchmark exposes the cost. A future partitioned ledger would require explicit ownership of payment IDs and source row keys. Readers are not globally locked.

## ADR-004: synchronous bounded batches

HTTP handles at most 2 MB/10,000 rows and returns a durable receipt. Airflow manages scheduled retries; there is no misleading fire-and-forget background task or in-memory queue. API responses distinguish accepted, replayed and quarantined input. Replaying an identical quarantined input returns the original receipt; correcting its content creates a new batch.

## ADR-005: use managed AWS services where justified

ECS Fargate suits this small API better than operating a Kubernetes control plane. Tasks and RDS use private subnets, with no task public IP or default Internet egress. ECR, logging and Secrets Manager use interface endpoints; S3 uses a gateway endpoint. The public ALB terminates TLS and drops invalid headers. S3 uses a rotating customer-managed KMS key and scoped task permissions. Private endpoints add hourly infrastructure cost. External partner HTTP requires a separately approved outbound connector or proxy; it is intentionally unavailable from the default private AWS task network. The local simulator exercises that adapter independently. The template currently uses an RDS owner account for initial schema creation; separate migration/runtime database roles are a production hardening requirement.

## ADR-006: explain decisions from a read snapshot

`GET /v1/reconciliation/{payment_id}/{currency}/explanation` and CLI `explain` share the domain classifier used by the normal reconciliation result. Three SELECTs read the original payment receipt, complete settlement aggregates with lineage validation, and a bounded, ordered bank-leg sample. The PostgreSQL connection uses read-only REPEATABLE READ, with a ten-second statement timeout; SQLite starts an explicit read transaction. The reader does not acquire the application's global writer advisory lock.

The evidence sample defaults to 25 legs and caps at 100. Exact totals and missing/wrong-kind/nonaccepted receipt checks cover the full group, including omitted legs. An explicit `truncated` flag prevents a sample from being mistaken for complete row-level evidence. Unknown currency groups return404, malformed parameters422, and broken stored lineage503. Both write and optional read tokens can inspect; anonymous access remains denied.

A source checksum records provenance. It is not proof that the raw object was re-read during explanation; the response explicitly returns `archive_integrity_checked=false`. The existing verify operation performs that separate integrity check. Tests commit a settlement through another connection during an explanation and demonstrate that the result keeps its original snapshot; the following request sees the committed settlement.

## ADR-007: scope measured work before applying result bounds

The evaluator generates an explicit set of payment IDs and restricts reconciliation to them before the 10,000-group response bound. Otherwise unrelated historical rows can hide the benchmark workload and produce an invalid correctness result. `test_evaluation.py` reproduces that case with more than10,000 older rows. The evaluator also records30 one-payment explanations alongside30 reconciliation/replay samples. These are reproducible local observations, not capacity or service guarantees.
