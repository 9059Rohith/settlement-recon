# OpenFX interview readiness audit — 5 November 2026

## Current AI recovery release

[Current source commits, hosted receipts, live API/provider observations and
remaining account blockers](ai-recovery-release.md) record the subsequent
transient-recovery and free-model-routing release. The earlier test counts and
runtime identities below retain their own scope and are not current uptime claims.

## Earlier same-day release: free hosted build gates

All four apps now have executed Vercel Linux build gates, with **771 default
tests passed and 64 explicit optional skips**, plus verified production promotion.
The final public API checks passed 14/14 and the latest real anonymous AI calls
passed for all four apps. Two initial AI503s and their successful cooldown retests
remain recorded. [Current release evidence, deployment identities and exact
GitHub/AWS blockers](free-hosted-ci.md) supersede the earlier runtime identities
below. GitHub Actions remains blocked before execution by an account billing
lock; workflow writes are unauthorized, and AWS credentials are unavailable.

## Honest assessment

These four repositories offer strong, complementary project evidence for both
internships. They are suitable for a technical interview demonstration, subject
to the limits below. A worldwide or applicant-pool "top 1%" ranking is unverified:
there is no representative comparison set or independent percentile assessment.
Code quantity, page count and visual polish cannot establish that ranking.

Data Engineering has the strongest directly executed coverage. DevOps has
substantial local/container/Kubernetes/observability evidence and actual public
hosting and actual free hosted build gates, but AWS operation and a successful
GitHub Actions run remain evidence gaps.
Project evidence cannot establish the applicant's SQL, Linux, networking,
debugging proficiency, degree eligibility or six-month availability.

## Earlier same-day verification results (before the build-gate release)

The final two changed runtime deployments were staged, checked through real
anonymous evidence-tool/model calls, promoted and resolved from their canonical
public aliases. Settlement Recon runs `a99fc42` on
`dpl_EwBJacKB2h6jJaqXLmiYWjmfMg2A`; DataGuard runs `38a0654` on
`dpl_13GD2XUkX95g1tLUMEkpWk6UwzUy`. The other two runtime deployments were
unchanged and retested. Documentation changes do not rebuild application behavior.
CI hardening is preserved as proposed patches because GitHub rejected workflow
file updates from the connected OAuth app without `workflow` scope.

| Project | Default suite passed / skipped | Focused native PostgreSQL passed / skipped | Distinct cases passed across both profiles |
| --- | ---: | ---: | ---: |
| Settlement Recon | 215 / 6 | 11 / 0 | 220 |
| FluxLake | 196 / 34 | 38 / 0 | 230 |
| DataGuard | 209 / 1 | 35 / 0 | 210 |
| PipeFoundry | 118 / 23 | 25 / 3 | 137 |

The profiles overlap; adding their pass counts would double-count some cases.
Their union is **797 distinct passing cases**, with five remaining skips: one
S3 integration opt-in, PipeFoundry's container/Spark opt-ins and two inapplicable
SQLite variants of durable-metadata recovery checks. Spark/container/Kubernetes
execution evidence from earlier runs retains its separate date and environment.
The focused PostgreSQL data paths were tested before the later AI-only transport
changes; those data implementations did not change.

After promotion, all **14 public API checks**, **eight desktop/mobile workflows**
at 390/1440 px and **four real anonymous Gemini requests** passed. The browser
flows observed no page/console errors, provider failures or horizontal overflow.
This covers the named primary workflows, not every possible interaction or an
uptime measurement. The initial two AI502s remain in the report. Error-level log
queries for the two final deployments returned no logs; no complete telemetry or
independent uptime audit is implied.

All four pinned runtime dependency audits reported no known vulnerabilities.
Ruff checks passed; the changed projects passed formatting and high-severity
Bandit checks. These are scoped source/dependency checks, not a new remote image
scan or proof of perfect security. The independent read-only review verified the
action pins and corrected source-byte wording and Retry-After edge cases before
release. [Machine-readable results and original logs](../evidence/interview-audit-20261105.json).

## What each project contributes

| Project | Strongest Data Engineering discussion | Strongest DevOps discussion | Important boundary |
| --- | --- | --- | --- |
| [Settlement Recon](https://github.com/9059Rohith/settlement-recon) | Exact currency arithmetic, multi-format ingestion, idempotency, source receipts and ambiguous allocation abstention | Non-root deployment, protected mutations, archived-input integrity and bounded compute-cost tooling | Public FX reference observations are not executed payments; AWS ECS/RDS/S3 is an unprovisioned profile |
| [FluxLake](https://github.com/9059Rohith/fluxlake) | Outbox ordering, tombstones, replay, immutable public acquisition and incremental SQL modeling | Crash recovery, safe connection-setup retries and reproducible publication/model experiments | Private SQLite/Parquet engine and public PostgreSQL workspace are distinct; managed AWS CDC/lakehouse is unverified |
| [DataGuard](https://github.com/9059Rohith/dataguard) | Data contracts, quarantine, atomic publication, version comparison SQL and source-backed policy experiments | Actual database/API outage alert transitions, startup recovery and protected metrics | Retained checks describe their evaluation time; no AWS failover, multi-AZ operation or production capacity result |
| [PipeFoundry](https://github.com/9059Rohith/pipefoundry) | Real Python ingestion and an executed Airflow/PySpark JSON-to-Parquet workflow | Real local K3s release/update/rollback, revision fencing and shared GitHub quota recovery | Public review does not launch workloads; local K3s is not EKS and Dag.test is not continuous scheduler operation |

## Supplied Data Engineering JD: requirement-to-evidence check

| Requirement | Evidence and status |
| --- | --- |
| Reliable batch and near-real-time pipelines | Settlement batch reconciliation and FluxLake bounded microbatch publication/model refresh are implemented and tested. Source poll delay, historical replay and actual source freshness are separate measurements. |
| Python and SQL extraction, transformation, validation | Actual parsers, parameterized SQL, model refresh and publication gates; API and database tests. |
| Structured and semi-structured sources | Payment JSON/bank CSV interfaces plus actual ECB, GitHub, GH Archive and NYC Open Data captures. Private financial data is not disclosed in public demos. |
| Ingestion, cleaning and quality checks | Normalization, identity checks, exact numeric bounds, durable rejection/quarantine and source-backed policy replay. |
| Spark, PySpark and Airflow exposure | PipeFoundry generated DAG completed through Airflow 3.3.2 Dag.test with PySpark 4.0.1 on 1,000 genuine NYC fare observations; independent DuckDB tuple/total readback. [Executed workflow](https://github.com/9059Rohith/pipefoundry/blob/main/docs/airflow-spark-proof.md). |
| Modeling for analytics and reporting | FluxLake SQL hourly event-type aggregates, applied-run ledger and share/rank view; independent full SQL/Python parity. [Model evidence](https://github.com/9059Rohith/fluxlake/blob/main/docs/incremental-hourly-model.md). |
| Monitoring, troubleshooting, optimization | FluxLake replay/recovery, DataGuard publication checks and measured query-plan improvement; explicit failure and timeout diagnostics. |
| Reliability, documentation and automation | Reproduction harnesses, runbooks, CI definitions and project-specific interview guides. Collaboration and learning ability require the applicant's own examples. |
| SQL joins, aggregation, query optimization, relational databases, ETL/ELT | Concrete code and tests support these topics. The interview must still demonstrate fluent reasoning and SQL writing without relying on AI. |
| AWS and lake/warehouse familiarity | Terraform/cloud architecture is reviewable; actual AWS managed processing is not established. Cloud familiarity is distinct from operating those services. |

## Supplied DevOps JD: requirement-to-evidence check

| Requirement | Evidence and status |
| --- | --- |
| Build/maintain cloud infrastructure, primarily AWS | Actual Vercel/Neon hosting and AWS Terraform definitions/validation. AWS apply, IAM execution, managed failover and ongoing operation remain unverified. |
| Infrastructure as Code / Terraform | Versioned VPC, compute/storage/identity configurations and provider validation. Validation alone is not a deployment. |
| CI/CD development and improvement | Nine workflow files, local equivalent checks, real Vercel staged promotion and newly executed Linux release-build gates. An immutable-action-reference patch is prepared and validated, but cannot be applied through the current OAuth connection; the account billing lock prevents a passing GitHub Actions run. |
| Docker, Kubernetes and containerized apps | Non-root images plus three actual completed K3s Jobs across guarded create/update/rollback. [Executed cluster evidence](https://github.com/9059Rohith/pipefoundry/blob/main/docs/kubernetes-release-proof.md). |
| Python/Bash scripts and automation | Actual ingestion, rendering, deployment, release verification, recovery and benchmarking commands. |
| Monitoring, logging, alerting and observability | DataGuard Prometheus rules reached pending/firing/inactive during actual local DB/API failures; no external pager delivery is claimed. [Alert drill](https://github.com/9059Rohith/dataguard/blob/main/docs/prometheus-alert-drill.md). |
| Reliability, performance and cost | Durable idempotency/fencing, bounded recovery and source-scoped benchmarks; Settlement's public AWS price-catalog estimator covers stated Fargate compute only. |
| Operational tooling, documentation and productivity | PipeFoundry typed-config-to-artifact/review workflow, backfills/rollback controls, troubleshooting and runbooks. Productivity improvements need measured baselines before claiming a percentage. |
| Linux/OS/networking fundamentals, Git, containers, debugging | Linux runtime/Kubernetes/Airflow execution and Git history provide practical exposure. The applicant still needs to explain processes, permissions, signals, DNS, TCP/TLS, routing, ports and failure diagnosis. |
| Security, scalability and ownership | Tested authentication/input boundaries, exact source provenance and explicit scaling bottlenecks. No independent penetration test or unbounded-scale claim. |

## Corrections and prepared fixes

1. Prepared patches pin **39 direct action references** across the repositories
   to 40-character commits resolved from official upstream repositories and
   disable persisted checkout credentials. Existing version labels remain as
   comments. GitHub rejected publication of the actual workflow file changes
   because the connected OAuth app lacks `workflow` scope. Active hosted workflow
   files remain unchanged. The complete rejected task commits are preserved on
   local `codex/openfx-workflow-hardening-20261105` branches, and applicable patches
   are published for review in each repository's `docs/workflow-hardening.patch`.
   [Prepared patch](workflow-hardening.patch) ·
   [Resolution provenance and scope blocker](../evidence/action-pins-20261105.json).
   This covers direct references, not every action's transitive dependency or
   mutable runner/container image. [GitHub guidance](https://docs.github.com/en/actions/reference/security/secure-use).
2. Project interview guides now distinguish hosted and private execution profiles,
   actual local experiments and unprovisioned AWS configurations. PipeFoundry's
   traceability now includes the executed K3s and Airflow/PySpark workflows.
3. Each README points to the same dated assessment and its own demonstration
   guide. Historical benchmark numbers retain their original scope and dates.
4. A fresh live check exposed generic AI HTTP 502 responses in Settlement Recon
   and DataGuard. Their underlying original causes were not logged, so no exact
   historical root cause is claimed. Both now have bounded transient recovery,
   provider-directed retry delays, safe diagnostics and minimal Gemini reasoning.
   [Settlement policy](public-ai-recovery.md) ·
   [DataGuard policy](https://github.com/9059Rohith/dataguard/blob/main/docs/public-ai-recovery.md).
5. Settlement Recon's stage-host allowlist mismatch was reproduced and corrected
   using only the exact Vercel-supplied deployment hostname. Five regressions
   preserve rejection of unrelated/wildcard/URL-shaped values and leave configured
   production hosts unchanged. A stale formatting failure in its CI formatting
   scope was also corrected without changing rendered behavior.

## What remains before stronger claims

- **AWS operating evidence:** credentials and a verified eligible Free account
  plan are unavailable. The reviewed profiles must remain design/IaC exposure
  until an authorized deployment can meet the free-only constraint. Public free
  hosting does not demonstrate AWS IAM/RDS/EKS/DMS operation.
- **GitHub Actions:** obtain a genuinely completed run after the account billing
  lock is resolved. The new Vercel Linux gates establish hosted verification,
  while GitHub Actions remains blocked. The proposed hardening also needs a connection authorized
  to update workflow files before it can be applied. No privilege escalation was
  attempted. Existing failed run outcomes are preserved in PipeFoundry.
- **Production operations:** individual identities/RBAC, versioned DB migrations,
  separately tested backup/PITR restoration, managed failover, retention and
  sustained concurrent capacity are broader production work, not completed claims.
- **Source freshness:** retained source observations are real and dated; they do
  not establish continuous ingestion or a live bank feed. Provider quotas can
  defer refreshes. Public AI has safe finite allowances and cannot guarantee every
  factual statement; inspect the returned source trace.
- **Applicant preparation:** reproduce at least one workflow per project and
  explain the transaction boundaries and failure cases below without reading a
  generated answer. A repository cannot certify interview performance.

## Practical interview checks

Before the interview, be able to:

1. Write a SQL join that does not multiply monetary totals when settlements have
   several legs; explain join cardinality and aggregate at the correct grain.
2. Explain why a greater outbox ID can commit before a lower one and why a simple
   high-watermark checkpoint can lose data.
3. Describe what commits atomically, what can remain orphaned and what a replay
   does after a process dies between storage boundaries.
4. Read EXPLAIN ANALYZE, distinguish estimated from actual work and reproduce the
   stated query improvement on the same workload.
5. Explain Spark partitioning, shuffles and deterministic deduplication; explain
   Airflow logical dates, task retries and why storage owns correctness.
6. Diagnose a failed container using process status, logs, events, resource limits,
   filesystem permissions, DNS resolution, TCP reachability and TLS validation.
7. Explain Kubernetes admission versus Job completion and why configuration
   rollback does not undo data already committed by a worker.
8. Explain least-privilege OIDC/IAM design and a private-network failure using the
   Terraform files, while acknowledging that this AWS profile is not deployed.
9. State a benchmark's dataset, sample count, timing boundary, environment and
   failure disclosures before quoting a percentile.
10. Give a concise ownership/debugging example from the actual implementation and
    distinguish your own work from generated tooling and external services.

The live checks and fresh test counts for this audit are recorded in
[the audit results](../evidence/interview-audit-20261105.json). Earlier full-runtime
and native PostgreSQL/Spark/Kubernetes proofs remain separately dated artifacts.
