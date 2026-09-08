# Azure live-demo evidence

This directory is populated by `.github/workflows/beastos-azure-live-demo.yml`.

The workflow may record only non-secret receipts, browser evidence, hashes, logs that have passed the Beast/Synapse redaction boundaries, and the status labels defined by the BeastOS Web Machine architecture. Azure credential values are never committed or copied into evidence.

A storage credential or an ambiguously named Azure key is not accepted as an AI inference credential. A live demo requires a distinct Azure AI/Foundry inference key, an OpenAI-compatible `/openai/v1` Azure endpoint (or derivable Azure AI resource/account name), and a deployment/model name.
