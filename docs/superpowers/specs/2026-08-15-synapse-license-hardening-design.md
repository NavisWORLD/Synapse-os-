# Synapse OS License Hardening Design

## Goal

Replace the permissive MIT licensing of future Synapse OS versions with a source-available dual-licensing model that preserves noncommercial evaluation access while requiring a separate written commercial license for business, redistribution, hosted-service, monetization, competitive product, and AI/ML uses of Cory Davis / NavisWORLD original material.

## Legal boundary

The new license applies only to original copyrightable material owned or controlled by Cory Davis / NavisWORLD and distributed in versions that contain the new license. It does not relicense Debian, third-party libraries, firmware, datasets, models, or other components governed by separate licenses.

The project must not claim that a license retroactively revokes rights validly granted under MIT for earlier copies or versions. Commit `3e7642d4b5c060ee0302ba769357e99c20dae98b` and earlier were publicly distributed with MIT terms for Synapse-specific original code. Recipients of those earlier copies retain the rights that were granted to them under the applicable earlier license.

The project must not claim copyright ownership over abstract ideas, methods, systems, algorithms, processes, or discoveries. The license may reserve any patent, trademark, contract, or other rights that independently exist, and may condition the limited source-available license on specified use restrictions.

## License model

### Public source-available grant

The public license grants only a limited, nonexclusive, nontransferable right to:

- view the covered source;
- reproduce and run it privately for personal, educational, security-review, or internal noncommercial evaluation;
- make private modifications solely for those permitted purposes;
- submit proposed contributions back to the official repository.

The grant does not authorize public redistribution of modified or unmodified covered material except repository forks/copies necessarily permitted through GitHub platform functionality. It does not grant sublicensing rights.

### Uses requiring a separate written commercial license

A separate signed commercial agreement is required before using covered original material for:

- commercial products or services;
- internal business operations beyond evaluation;
- paid consulting or client deliverables;
- SaaS, hosted, managed, cloud, API, appliance, embedded, OEM, or resale offerings;
- redistribution, sublicensing, resale, or bundling;
- commercial derivative products or competing implementations materially derived from covered source;
- AI/ML training, fine-tuning, distillation, dataset construction, embeddings, retrieval corpora, benchmark/evaluation corpora, synthetic-data generation, or model-development pipelines using covered material.

## Reserved rights

The license reserves all rights not expressly granted. No patent license is granted. No trademark, service-mark, trade-name, logo, or branding license is granted. No permission to imply sponsorship, endorsement, affiliation, certification, or official compatibility is granted.

The project may use `TM` for claimed unregistered source identifiers where appropriate, but must not use the federal registration symbol unless a registration is actually documented.

## Historical licensing

Create a clear `LICENSE-HISTORY.md` identifying the MIT-era boundary and explaining that the new license does not claw back earlier grants. The README and licensing guide must no longer describe the current version as MIT licensed.

## Contributor rights

Future external contributions are accepted only under contributor terms that:

- require the contributor to represent that they have authority to contribute the material;
- license the contribution to Cory Davis / NavisWORLD on a perpetual, worldwide, irrevocable, royalty-free, sublicensable basis;
- expressly allow Cory Davis / NavisWORLD to use, modify, distribute, commercialize, and relicense the contribution as part of Synapse OS;
- preserve the contributor's ownership unless a separate written assignment says otherwise;
- require an explicit pull-request acknowledgement of the contributor terms.

## Repository metadata

Update all first-party package manifests and public documentation that currently state `MIT` so they reference the custom license or root license file instead. Rust must use `license-file`; Python packaging must use a custom license text rather than `MIT`.

## Third-party materials

Add a third-party licensing notice explaining that generated Synapse OS images aggregate Debian and other packages under their own licenses. Nothing in the custom Synapse license may restrict rights granted directly by those third-party licenses.

Publicly disclosed Synapse source is not treated as a trade secret. Any confidential know-how intended for trade-secret treatment must remain outside the public repository and be protected through actual secrecy measures and appropriate agreements.

## Enforcement in CI

Add a repository license-audit script and tests. `make check` must fail if:

- required legal files are missing;
- the root license is replaced with MIT or another permissive declaration;
- README/docs/package manifests reintroduce current-version MIT licensing;
- Rust or Python package metadata reintroduces `MIT` licensing;
- contributor terms or commercial-licensing notices disappear.

The audit may explicitly allow historical references to MIT inside `LICENSE-HISTORY.md` and legal design/plan documentation.

## Files

Create:

- `COMMERCIAL-LICENSING.md`
- `LICENSE-HISTORY.md`
- `NOTICE`
- `TRADEMARKS.md`
- `THIRD_PARTY_NOTICES.md`
- `CONTRIBUTOR_LICENSE_AGREEMENT.md`
- `CONTRIBUTING.md`
- `.github/pull_request_template.md`
- `scripts/license_audit.py`
- `tests/test_license_policy.py`

Modify:

- `LICENSE`
- `README.md`
- `docs/LICENSING.md`
- `CORY_DAVIS_IP_AND_ACCESS_NOTICE.md`
- `pyproject.toml`
- `sdk/rust/Cargo.toml`
- `Makefile`

## Verification

The branch is acceptable only after:

1. license-policy unit tests pass;
2. `scripts/license_audit.py` passes;
3. full `make check` passes in GitHub CI;
4. repository diff contains no unrelated code changes;
5. current `main` receives the policy through a reviewed/verified pull request.
