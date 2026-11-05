# OpenFX interview audit implementation plan

> Execute natively in this session; the user explicitly requested fixes without questions.

**Goal:** Remove verifiable delivery and explanation gaps without inventing a percentile ranking or AWS execution evidence.

**Scope:** Supplied OpenFX internship PDFs; four independent repositories and existing public deployments. Preserve real source data, current operator boundaries and bounded public AI allowances.

## Tasks

- [x] Run all four default regression suites into `output/openfx-interview-audit/`; distinguish optional integration skips from the earlier executed PostgreSQL, Spark and Kubernetes reports.
- [x] Resolve the exact current action tags used by the nine workflow files from each official action repository using `git ls-remote`, including peeled annotated tags. Save public provenance; replace tags with full commit IDs and preserve version comments. Disable persisted checkout credentials. Parse YAML, verify every direct action reference, and inspect affected workflows before committing.
- [x] Reconcile `docs/interview.md`, DataGuard `docs/INTERVIEW.md`, and PipeFoundry `docs/requirements.md` with actual public/private execution profiles and current benchmark evidence. Add short, project-specific demonstration steps and explain failure modes, implementation boundaries and AWS/CI limitations.
- [x] Update the central `docs/openfx-jd-coverage.md` and add a dated evidence-based assessment. Name precise DE and DevOps evidence, source provenance, metric scope and remaining external gaps. Link it from each project README.
- [x] Run current public API and browser checks without consuming more model allowance unnecessarily. Existing successful live model requests retain their original date/scope; never relabel them as new calls.
- [x] Address the two observed live AI502s: reproduce bounded provider-fault handling with failing tests; add safe diagnostics and one shared read-only retry, respect Retry-After, rerun affected full suites, stage/promote both runtime fixes and verify real public AI responses. The exact initial upstream causes remain unconfirmed because the prior handlers did not retain them.
- [x] Publish verified repository changes. Application deployment is required only if runtime files change; CI/docs changes do not require rebuilding unchanged live services.

## Verification and review

Full default suites plus focused regressions for any observed failure; exact action/tag provenance and YAML inspection; point-in-time runtime dependency audits; canonical public source reads, replay, release review and rejected anonymous mutations. No automatic AWS provisioning, paid resources, unprotected executor mutations or claimed hosted CI success.

Review likely mistakes: confusing local SQLite with public PostgreSQL, calling an outbox WAL CDC, calling static review a live cluster deployment, reporting captured data as fresh, and extrapolating local benchmark percentiles to cloud SLAs.

## Completion evidence

Final results: 797 distinct passing cases across overlapping default and isolated PostgreSQL profiles, five optional/inapplicable skips, 14 public API checks, eight mobile/desktop workflows and four real public AI answers. Runtime fixes were staged and promoted for Settlement Recon and DataGuard; FluxLake/PipeFoundry runtime code remained unchanged. Interview materials are published separately. CI hardening is delivered as applicable patch files because GitHub rejected workflow updates without OAuth workflow scope.

Ruling: the live audit expanded scope to two AI502 responses and an exact-host staging failure. Their code changes used failing regressions before implementation. The specific original upstream AI causes remain unconfirmed; bounded recovery and safe diagnostics are verified rather than asserting a historical cause.

Ruling: an initial disposable DataGuard database name was rejected by the existing _test safety guard. The harness was corrected rather than weakening that guard; the corrected focused suite passed35 tests.

External blocker: GitHub rejected workflow publication because the OAuth App lacks workflow scope. Rejected task commits are retained on local codex/openfx-workflow-hardening-20261105 branches. Each repository publishes a checked docs/workflow-hardening.patch; active workflows remain unchanged. Only non-workflow documents/evidence are published through the current connection. No alternative credentials or privilege escalation were attempted.
