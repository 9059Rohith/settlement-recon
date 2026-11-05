# Free hosted verification gate plan

**User constraints:** no questions, no paid resources, real tests/deployments, retest all four apps.

**Observed external blockers:** GitHub job annotations in all four repositories say the account is locked due to a billing issue. GitHub App workflow updates also return403; Git OAuth lacks workflow scope. SDK has no AWS profiles or credentials. Browser automation stopped for URL-policy enforcement and must not be retried or bypassed in this turn. No AWS account/plan access can be verified, so no AWS provisioning is authorized under the free-only constraint.

**Available free path:** the already-authorized Vercel CLI reports team `team_WkR0cDVyRzw7XTRitQwgfgJc` is active Hobby. Add actual Linux build-time verification to each existing multi-stage Docker build. This is Vercel-hosted CI, explicitly separate from the account-blocked GitHub Actions workflows.

## Independent repository tasks

1. Settlement Recon: preserve the scoped static-HTML Bandit false-positive fix; add a verification stage with actual tests, source checks and a generated receipt.
2. FluxLake: make its existing verification stage execute during the release build, instead of merely defining a test CMD that the runtime target never consumes.
3. DataGuard: add a build-time verification stage without carrying test dependencies into runtime.
4. PipeFoundry: add a build-time verification stage without optional Spark/PostgreSQL credentials; retain meaningful skips and existing independent integration evidence.

## Contract for every gate

- Keep runtime package pins and hardened production image unchanged.
- Verification uses pinned test tools; never pull production env files or send credentials/prompts to test logs.
- Include required tests/scripts/config/docs fixtures in the pruned build context; keep `.git`, `.vercel`, `.env*`, private runtime/state data, credentials and prior evidence excluded.
- Run lint/security checks where available and the actual full default pytest suite. No ignored failure, fake green result or fabricated test totals.
- Generate a non-sensitive JSON receipt only after passing real commands, parsed JUnit pass/failure/error/skip counts and source/test/lock fingerprints. Skipped integration opt-ins remain explicit.
- The final runtime stage must COPY that small receipt from verification so the builder cannot omit the test stage. No test tools or fixtures enter the runtime image.
- Validate scope/negative gate behavior with meaningful tests. Stage production on the existing Hobby project, inspect actual build logs, then check readiness and source workflows before promotion.
- Save build/deployment evidence and retest all four public APIs and one real bounded anonymous AI call per app. No further browser automation after the current turn's policy stop.

The build gate does not claim AWS deployment, GitHub Actions success, full managed-service coverage or zero vulnerability risk. The final report must identify those remaining account/access blockers precisely.
