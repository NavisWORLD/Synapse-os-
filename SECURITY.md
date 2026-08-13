# Security Policy

Do not commit API keys, COSMOS `.env` files, private weights, personal memories, SSH keys, or signing keys to this repository.

Synapse Flow intentionally has no arbitrary shell execution. The telemetry agent is local-only and writes to `/run/synapse/status.json`; it has systemd hardening enabled.

Report security issues through the repository's GitHub issue/security channels without posting live credentials or personal data.
