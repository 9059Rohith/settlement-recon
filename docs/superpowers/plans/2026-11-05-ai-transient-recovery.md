# AI transient recovery implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task.

**Goal:** Recover bounded transient AI faults in four independently deployed apps, retain free-only operation, and verify actual releases.

**Architecture:** Each project's existing provider adapter owns a shared investigation budget. Retry only transient provider/network faults without replaying completed tools. Existing public database rate limits and real read-only source tools remain unchanged. Existing Vercel Linux release gates remain the free AWS alternative.

**Tech stack:** Existing Python/FastAPI transports, pytest, native JavaScript helpers, Vercel Hobby, Neon, existing free Gemini configuration.

## Constraints and review focus

- No questions, paid resources, payment changes, new credentials, fabricated answers or fabricated passing workflow statuses.
- Shared request ceiling six; shared transient retry ceiling two; deadline no more than 60 seconds and each request bounded by remaining time.
- Valid provider Retry-After must never be shortened; nontransient 4xx and invalid protocol responses must not become retry storms.
- Preserve operator authentication, public quotas, fixed provider origins, source evidence and private/public boundaries.
- Logs contain status/type/attempt only, never prompts, keys or provider bodies.
- Failed live attempts stay in the evidence; browser automation success is not assumed.

## Tasks

1. Recheck current GitHub run annotations. If the account billing lock remains, retain the exact source-commit evidence and document supported account resolution; do not change billing or pretend deployment gates are GitHub Actions runs.
2. For each project, reproduce missing/insufficient transient recovery in regression tests before implementation. Cover two overloads, exhausted shared retries, deadline, nontransient faults, quota and provider cooldown.
3. Implement the narrow transport fix. Correct numeric/date cooldown parsing in UI helpers where investigation finds a defect. Run relevant JavaScript tests and the full default Python release gate, preserving optional integration skips.
4. Review independent changes, publish non-workflow commits, stage on the existing free Vercel project, verify actual hosted gate receipts and source workflows, then promote the same builds.
5. Retest all four public readiness/data/replay/review/authentication paths and real anonymous AI/tool calls. Publish new release identities and all observed live outcomes alongside the precise GitHub/AWS boundaries.
