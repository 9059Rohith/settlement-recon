# GitHub Actions account lock: evidence and free-only resolution

The latest observed runs in all four public repositories fail before runner
steps start. Their check annotations state:

> The job was not started because your account is locked due to a billing issue.

This is not a repository test failure. See each repository's dated
`evidence/free-hosted-ci/github-latest-run.json` or newer release evidence for
the exact commit, run URL, empty steps and annotation.

[GitHub's account-lock documentation](https://docs.github.com/en/billing/how-tos/troubleshooting/locked-account)
explains that failed payment authorizations can block Actions even on Free
accounts. It describes account downgrade or billing resolution where applicable,
and Support review when no active subscription, balance or issue is visible.
The annotation alone does not establish which account-specific cause applies.

The available repository integration cannot manage this account billing lock.
An additional authenticated capability check confirmed that its connected
identity differs from the affected personal repository owner. The connector
does not expose account billing, plan-management, runner-registration or account
unlock tools. Repository write access is not personal-account billing authority.
It also rejects workflow-file writes with HTTP 403. The ordinary Git OAuth
connection previously rejected workflow updates without workflow scope. Existing
reviewed patches are retained in `docs/workflow-hardening.patch`; their presence
does not imply that active workflow files were changed.

No payment method was read or changed, no authorization charge was initiated,
no paid subscription was enabled, and no account downgrade was performed. A
downgrade can affect unrelated account features, so it is not a repository fix.
The existing Vercel Hobby release gates provide executed hosted tests without
claiming that GitHub Actions passed.

Standard public-repository hosted runners already qualify for free compute.
Registering a self-hosted runner requires administration that is unavailable in
this connection, and GitHub does not document it as a bypass for this account
lock. Downgrade timing and unrelated Copilot/Marketplace billing are separate
from changing the repository's runner. See
[runner prerequisites](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)
and [plan-change effects](https://docs.github.com/en/billing/concepts/impact-of-plan-changes).

## Ready-to-use Support request (draft, not sent)

Subject: Review billing lock blocking free Actions in public repositories

Account: `9059Rohith`

Standard GitHub Actions jobs in these public repositories are blocked before
any steps start: `settlement-recon`, `fluxlake`, `dataguard`, and `pipefoundry`.
The exact annotation is recorded above, with public run URLs in the attached
repository evidence. Please review the account billing/authorization lock and
restore eligible GitHub Free Actions access. Please do not enable a paid plan,
paid runners, an increased spending budget, or a billable authorization as part
of this request.

This draft has not been sent to GitHub or another person. The private billing
state must be resolved through the account's supported billing/Support channel;
changing Python, YAML or Terraform cannot remove the server-side account lock.
