# Interview questions and defensible answers

## Current interview demonstration

Start with the [public overview](https://rohith-settlement-recon.vercel.app/workspace/overview)
and [historical replay](https://rohith-settlement-recon.vercel.app/workspace/history).
Replay USD/INR for 1–7 January 2025: four paired reference observations are
expected. Explain the original quote dates, retained provider response and exact
cross-rate calculation. These are real public currency reference observations,
not executed cross-border payments or a live bank integration.

Then show the private reconciliation engine in code: parsing and precision,
receipt/checksum identity, atomic rejection, duplicate replay and ambiguous
allocation abstention. Correctness tests deliberately include synthetic edge
cases. Public source captures and controlled test fixtures have separate scope.

For the Data Engineering role, explain one ingestion-to-SQL path and the effect
of a duplicate or invalid batch. For DevOps, explain non-root containers,
health versus readiness, protected writes, deployment rollback and the bounded
AWS compute estimator. The actual public deployment is Vercel/Neon. The ECS,
RDS and S3 Terraform profile has not been provisioned on AWS.

The [current portfolio audit](openfx-interview-readiness.md) links requirements
to executed evidence and records the remaining AWS/hosted-CI gaps.

## Engineering questions

1. **Why integer minor units?** Floating-point addition can change equality comparisons. We accept decimal strings, validate currency precision and store exact integers; fees and settlement amounts are summed within currency only.
2. **Is processing exactly once?** Transport is retryable and can repeat. Stable source/business keys, immutable receipts, a serialized transaction and unique constraints provide one business effect for identical input. This is not a general distributed exactly-once guarantee.
3. **What if the process dies after S3 upload?** There may be an unreferenced raw object. No business rows committed; replay reuses the checksum and starts a new database transaction. A distributed transaction across S3 and PostgreSQL is not attempted.
4. **Why reject an entire conflicting batch?** Publishing its other rows would make upstream correction and accounting ambiguous. Raw evidence and errors remain available; the operator fixes the source and submits new bytes. Real adjustment records need an explicit future design.
5. **Why a global advisory lock?** It makes the ownership/duplicate race straightforward across workers. It bounds write throughput; the project measures this instead of claiming unlimited scale. Partitioning requires clear key ownership and careful cross-partition settlement semantics.
6. **How did you improve performance?** A query-budget regression initially measured 603 statements for 200 rows. Bulk prefetch and executemany insert replaced per-row existence queries. Compare the measured before/after JSON under evidence on the stated machine; do not extrapolate them into cloud SLAs.
7. **Why does the AWS configuration choose ECS instead of Kubernetes?** A bounded ingestion API does not need a cluster control plane. The optional Fargate profile expresses networking, IAM, container delivery, health and rollback. It has not been applied on AWS; the actual public app uses Vercel/Neon. PipeFoundry has separate executed local Kubernetes evidence.
8. **How do you distinguish a successful upload from correct data?** HTTP 200 is only a durable ingestion receipt. Its status can be quarantined. Reconciliation separately reports missing/partial/overpaid/orphan groups; archive verification checks provenance integrity.
9. **What is still needed before regulated production?** Independent security review, individual identities, rate limits, tested disaster recovery, migration/runtime DB-role separation, retention/legal controls, broader accounting semantics and live workload testing. No compliance certification is claimed.
10. **Can you reproduce the result?** Fresh clone, pinned dependencies, generated local credentials, Compose, CLI demo, full tests and benchmark script. PostgreSQL integration needs TEST_DATABASE_URL; the AWS profile needs account-specific inputs. Evidence records what was actually run.
11. **How do you explain an exception without inventing evidence?** One rule implementation classifies both summary and explanation. A read-only PostgreSQL REPEATABLE READ transaction reads the payment, complete settlement totals/receipt checks, and a capped bank-leg sample. Every returned leg references its original batch/checksum. A concurrent writer test proves the three SELECTs do not combine different committed snapshots.
12. **Does an explanation verify the original file?** No. It identifies the retained input checksum and receipt; `archive_integrity_checked=false` is explicit. The separate verify route reads the archived bytes and checks SHA256. Neither protects against a compromised database owner.
13. **What did a benchmark regression reveal?** A global result limit can exclude newly generated benchmark rows when a shared database contains older records. The evaluator now restricts its generated IDs before the cap, asserts exact matches, and measures one-payment explanations separately. A test seeds10,001 unrelated records to keep that measurement failure reproducible.
