# Hosted backup model verification plan

> **For agentic workers:** Use the normal implementation, review and verification workflow; the user has opted out of questions.

**Goal:** Run PipeFoundry's real secondary model through the deployed public tool loop, restore the normal preferred-model configuration, and retest four public apps without paid resources.

**Design:** A server-only incident-control setting accepts exactly the two existing free Gemini models. The existing public API remains question-only, with fixed repository, provider endpoint, authentication boundaries and database quotas. Invalid settings fail closed for AI without taking down unrelated integration status. No key is retrieved, printed, downloaded or committed.

## Tasks

1. Recheck GitHub run/capability evidence. Verify whether a legitimate free account-level resolution is executable; do not change billing, contact others, bypass permissions or mislabel non-Actions CI.
2. Reproduce and test preferred-model selection, backup pinning, invalid settings before reservations/inference, accurate public status/UI, operator isolation and rejected public overrides. Run PipeFoundry's full release gate and native JavaScript tests.
3. Independently review the selector and tests. Publish source; stage the exact commit using the deployment-scoped nonsecret selector for the secondary model. Verify hosted gate, readiness and real source workflows.
4. Verify an actual secondary-model response with provider usage/request evidence and real GitHub tool trace. Keep observations, including failures, and do not use fault injection to claim a live outage.
5. Stage the same commit with the normal primary selection, verify its gate and public workflows, promote the tested build, then retest all four APIs and anonymous agents. Record configuration differences, exact deployment IDs and remaining account blockers.

## Constraints

- Existing Vercel Hobby/Neon resources only; no AWS apply or paid upgrade.
- Two approved server-selected models only; no caller override or new provider.
- Existing limits, deadlines, retry budget and conversation signature boundaries remain intact.
- Secondary-model inference verification is distinct from automatic outage routing; the latter retains controlled-fault tests.
- A passing local or Vercel build is never represented as a passing GitHub Actions run.
