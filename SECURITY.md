# Security model

Use only synthetic data in the public demonstration. This service is not certified for PCI DSS or regulated payment processing.

The [actual public deployment](docs/public-deployment.md) uses a minimal,
digest-pinned Python3.15.1 image and isolated Neon PostgreSQL with verified TLS.
Its latest all-severity image scan reports zero vulnerabilities and zero secrets;
the earlier Debian cached scan in historical evidence is superseded. Public demo
aggregation is restricted to its known synthetic source and IDs. Raw records and
administrative operations remain protected. The new database archive preserves
and verifies raw input across ephemeral-container restarts. Concurrent schema
bootstrap is serialized; authenticated uploads have a bounded read deadline.

- Business APIs and metrics require constant-time bearer-token comparison. Write and optional read tokens have separate privileges. Missing/short writer credentials disable all protected operations. Rotate by updating the secret and restarting containers/tasks. TLS is required outside loopback.
- Inputs have byte/row bounds, strict schemas, safe identifier syntax, decimal precision and timezone validation. SQLAlchemy binds values; source identifiers cannot become file paths or SQL fragments.
- The operator-only partner connector requires explicit allowed hosts, HTTPS (except named loopback for the local simulator), no userinfo/redirects, bounded responses/timeouts and three transient retries. Operators must use trusted DNS and outbound network controls; hostname allowlisting alone is not a complete DNS-rebinding defence.
- The container runs as UID10001, drops capabilities and uses a read-only root with a dedicated writable data volume in Compose. AWS tasks and PostgreSQL use private subnets; tasks have no public IP/default Internet egress and accept application traffic only from the TLS ALB. Regional API traffic uses VPC endpoints and S3 uses its gateway prefix list. PostgreSQL is accessible only from the application security group.
- Raw S3 access is scoped to one bucket/prefix and excludes deletion. AWS uses a rotating customer-managed KMS key, a bucket key and KMS permissions restricted to regional S3 use. Local MinIO tests use AES256 encryption with an explicit test-only KMS configuration. Public-access blocking and versioning are configured. Database backups and deletion protection are enabled. Backups still require an actual restore exercise before production use.
- No input payloads, tokens or database URLs are written to HTTP logs. Audit receipts contain source/checksum/status/timestamps and generic validation errors. Raw objects do contain source records and require appropriate retention/access policies.

## Verification boundary

CI performs Ruff, Bandit, a locked runtime dependency audit, negative tests, PostgreSQL integration, Terraform validation and a Docker build. Record dates/results in `VERIFICATION.md`. These checks do not establish perfect security. Static analysis is limited; authenticated penetration testing, independent audit and load/abuse protection remain production work.

Known limits: shared bearer secrets rather than individual OIDC identities, no per-client rate limiter, global write serialization, application-created schema rather than a migration framework, and owner-level initial RDS database access. AWS IAM/secret rotation/TLS policies are configured but unverified in a live account until deployed. Do not expose the local development port through a public tunnel.

For a suspected issue, open a private GitHub security advisory rather than publishing credentials or financial records in an issue. Never commit `.env`, Terraform state, access tokens or database dumps.
