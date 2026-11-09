# Historical fixing desk implementation plan

**Goal:** Give recruiters a working, reproducible financial-data workflow rather than another static architecture page.

**Architecture:** A pure bounded Python service values visitor-authored dated amounts against the original pinned ECB archive. The existing historical replay page gains a separate accessible desk and JSON export. No extra provider, data mutation, or AI request is required.

**Design decisions:** Use the latest actual paired observation on or before each date; never use future quotes. Missing or over-age pairs remain unvalued. Exact rational arithmetic drives integer half-even rounding. Show row-rounding versus aggregate-rounding differences. The retained archive end date stays visible. Inputs are not represented as real customer payments.

**Files:** `fixing.py`, `fixing.js`, existing workspace routing/UI/CSS, `tests/test_fixing.py`, a reproducible benchmark, and documentation.

- [x] Tests first: weekend/no-lookahead, stale/missing currency, rounding ties, identity, partial totals, duplicate keys/IDs, body bounds, foreign origin, no operator access.
- [x] Implement pure valuation and bounded route; keep existing authentication and public AI limits.
- [x] Add usable row-entry/validation, visible evidence and downloadable report in the existing visual style.
- [x] Run full tests, lint, formatting, JS checks, dependency/security checks, and a real-archive benchmark.
- [x] Attempt the existing free Vercel staged release; record the actual account-wide fair-use rejection and all four disabled public URLs. No build/promotion was possible. Source and local verification were published instead.

**Portfolio coordination:** Parallel agents own FluxLake portable replay evidence, DataGuard policy/source attribution, and PipeFoundry pipeline rehearsal in their separate repositories. Existing unrelated files are preserved.

**Limits:** Bounded portfolio workflows cannot establish a world ranking or institutional production reliability. AWS and GitHub account restrictions remain separate from these upgrades.
