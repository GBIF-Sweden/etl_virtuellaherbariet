# Release Hardening

## Dependency discipline
- Keep all runtime and dev dependencies pinned (`==`) in:
  - `requirements.txt`
  - `requirements-dev.txt`
- Update dependencies in controlled batches and run full CI before merge.

## Security checks
- CI enforces:
  - `pip-audit` for Python dependency vulnerabilities
  - `trivy` filesystem and image scans

## Container release policy
- Publish container images from version tags (`v*`) only.
- Use immutable image tags in deployments.

## Signing policy
- Recommended: sign release images with `cosign` and verify signatures at deploy time.
- Keep signing key material outside repository (secret manager / CI secrets).

## Required release evidence
- Passing CI for target commit
- Latest strict-mode run report (`quality_report_*`) for target herbarium/config
- Matching reconciliation report (`reconciliation_*`) with checksum recorded
