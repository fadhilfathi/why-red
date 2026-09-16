# Security Policy

## Supported versions

Only the latest minor release is supported with security fixes.

## Reporting a vulnerability

Report privately via GitHub's private vulnerability reporting:
https://github.com/fadhilfathi/why-red/security/advisories/new

Do not open a public issue for security reports.

## What counts

- Token or credential leakage (including through logs or `--ai` payloads).
- A bypass of fixture redaction that exposes real secrets.
- Any code path where why-red writes to GitHub instead of reading (it must remain read-only).

## Response target

We aim to respond within 7 days of a report.

## Bounty

No bounty program.
