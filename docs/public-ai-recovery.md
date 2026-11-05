# Read-only AI recovery boundary

The 5 November interview audit observed one public AI HTTP 502. Its original
upstream status/exception was not retained by the old generic handler, so the
specific cause is unconfirmed. A successful earlier request does not establish
that every future provider request will complete.

The reference-rate agent now has two transient retries shared across the whole
investigation, up to three model rounds and six provider attempts. The waits
increase from one to two seconds, with at most 100 ms of jitter. HTTP
500/502/503/504 and HTTPX network/timeout errors can use that allowance.
An exhausted transient failure returns HTTP 503 with Retry-After; quota errors
remain HTTP 429. A valid positive-seconds or future HTTP-date Retry-After is
propagated without an early retry. Other HTTP errors and malformed protocol
responses remain errors, never replacement analyses.

Before each attempt, a monotonic 60-second scheduling budget is checked; the
HTTPX timeout is at most 20 seconds or the remaining budget. Retry scheduling
reserves at least one second for the next response, and late successful responses
are rejected. These are blocking
client phase/inactivity timeouts and between-call checks, not hard wall-clock
cancellation of an active socket. Gemini requests minimal reasoning, with the
existing output-token bound. No alternative paid provider is selected on failure.

Only the failed read-only provider call can be retried. A completed evidence tool
is not executed again merely because the subsequent model call failed; its
original message and tool result remain in the conversation. No payment, source
sync or publication endpoint is added to the agent. The persistent public demo
allowance is reserved once before inference; retries still consume provider quota.

Warnings retain only phase, upstream HTTP status, exception class and attempt
count. Keys, prompts, source payloads, provider error bodies and database URLs
are not logged by this handling. Controlled fault regressions exercise the real
service-status tool loop, exhausted recovery, HTTP 400, timeouts, Retry-After,
expired budgets and credential/body redaction. Controlled responses are test
faults; public source records remain actual dated reference observations.

The form parses numeric and HTTP-date Retry-After values into a finite cooldown.
Provider failures do not automatically resubmit a visitor's question or bypass
the persistent public allowance. Retry delays do not become fabricated answers.

See [the portfolio audit](openfx-interview-readiness.md) for final deployment and
live verification results. Provider availability and the semantic accuracy of
generated prose cannot be guaranteed; inspect the source trace.

Staging also exposed a host-allowlist mismatch. With an existing allowlist and
VERCEL=1, the API now adds only the exact validated VERCEL_URL hostname supplied
by the platform. Wildcards, unrelated deployment hosts and URL-shaped values
remain rejected. Five regressions cover those boundaries without mutating the
caller's configured host list.
