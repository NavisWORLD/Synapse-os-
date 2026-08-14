# Zeref-Mobile-v1 // Synapse OS Integration

This folder is the Synapse OS / OS+ discovery and provenance lane for the native Apple `Zeref-Mobile-v1` artifact. It is intentionally developed on `feature/zeref-mobile-v1-integration` until its integration checks are reviewed.

The model itself is owned by the COSMOS lineage. Synapse OS does **not** rename, rewrite, or claim authorship over its checkpoint lineage.

## Artifact identity

- lineage: `Zeref-Mobile-v1`
- parent: `Zeref-Recovery-v2-CausalSigma`
- parent checkpoint SHA-256: `bb551d68980bdd5f1f0d20fb25c1974340420439b4dc8462b2b2f154a4b6a553`
- parent tokenizer SHA-256: `ba7c88eb0e210fa69f503c526a8ff96f5d0b5f58c614c8e74bb73ff1d34bbaea`
- package: `zeref-mobile-v1.cosmosmodel`
- package bytes: `144433`
- package SHA-256: `8ead952e3d14f00027a4017e4c891854eb99dcce025b6415f12c2765950f106d`
- q8 payload bytes: `132932`
- q8 payload SHA-256: `b6bb2e91f86b90a7f6fcbdf7d070cbb4120f70633f07e1d8a3bbc41ef46dbde7`
- runtime label: `MOBILE`
- runtime mode: `native-q8`
- telemetry: `cosmos-biostate-v1`

## What Synapse OS does

Synapse can verify and stage the package as an artifact for transfer/discovery. The package targets the native COSMOS Apple application; Synapse's Debian runtime does not claim to execute the iOS/Swift application itself.

Use `verify_cosmosmodel.py` to verify package identity and internal q8 integrity before transferring it to an Apple device.

## Source of truth

Implementation and exporter source live in the COSMOS Apple/mobile lane:

- repository: `NavisWORLD/Cosmos`
- branch: `feature/cosmos-apple-zeref-mobile-v1`
- app: `apps/apple/`
- model source: `models/zeref-mobile-v1/`

The deterministic exporter is byte-locked: an artifact drift requires a reviewed new model/version instead of silently inheriting the `Zeref-Mobile-v1` name.

## Truth boundary

Portable Swift verification is not the same as a physical-iPhone run. Synapse should display Simulator/device provenance separately, and 12D software telemetry must not be labeled as biological feeling or proof of consciousness.
