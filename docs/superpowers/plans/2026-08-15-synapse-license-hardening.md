# Synapse OS License Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace permissive MIT licensing for future Synapse OS versions with the Cory Davis / NavisWORLD Synapse Source License 1.0 dual-licensing model and enforce the policy across repository metadata, contributions, documentation, and CI.

**Architecture:** The root `LICENSE` is the controlling first-party source license. Supporting legal files define commercial licensing, history, trademarks, contributor rights, third-party carve-outs, and provenance. A Python audit plus unit tests make license drift a build failure through `make check`.

**Tech Stack:** Markdown legal/policy documents, Python 3.11 standard library, TOML package metadata, GNU Make, GitHub pull-request templates.

## Global Constraints

- Do not claim retroactive revocation of valid MIT rights for earlier copies or versions.
- Do not relicense Debian or other third-party components.
- Do not claim copyright in abstract ideas, systems, algorithms, methods, or discoveries.
- No current-version first-party file may describe Synapse OS original code as MIT licensed.
- Commercial, hosted-service, redistribution, competitive-product, and AI/ML uses require a separate written commercial license.
- No patent or trademark license is implied by the public source grant.
- Publicly disclosed source is not represented as a trade secret.
- Historical MIT references are allowed only in designated history/legal documentation.

---

### Task 1: Replace the controlling license and add legal package

**Files:**
- Modify: `LICENSE`
- Create: `LICENSE-HISTORY.md`
- Create: `COMMERCIAL-LICENSING.md`
- Create: `NOTICE`
- Create: `TRADEMARKS.md`
- Create: `THIRD_PARTY_NOTICES.md`

**Interfaces:**
- Produces: the controlling first-party license and supporting legal/provenance documents consumed by repository docs and package metadata.

- [ ] Replace the MIT root license with `Cory Davis / NavisWORLD Synapse Source License 1.0`, including definitions, limited noncommercial evaluation grant, prohibited uses, commercial licensing requirement, AI/ML restriction, third-party carve-out, reserved patent/trademark rights, termination, warranty/liability disclaimer, severability, and historical-license preservation.
- [ ] Add `LICENSE-HISTORY.md` naming commit `3e7642d4b5c060ee0302ba769357e99c20dae98b` and earlier as the public MIT-era boundary for original Synapse-specific code.
- [ ] Add `COMMERCIAL-LICENSING.md` defining categories that require separate written permission and clarifying that no commercial rights arise from inquiry, download, fork, issue, or pull request.
- [ ] Add `NOTICE` with copyright, license reference, ownership limitation, and third-party notice.
- [ ] Add `TRADEMARKS.md` reserving claimed marks and forbidding implied endorsement while explicitly avoiding any representation of federal registration unless documented.
- [ ] Add `THIRD_PARTY_NOTICES.md` preserving Debian and dependency license rights.

### Task 2: Add contributor licensing controls

**Files:**
- Create: `CONTRIBUTOR_LICENSE_AGREEMENT.md`
- Create: `CONTRIBUTING.md`
- Create: `.github/pull_request_template.md`

**Interfaces:**
- Produces: future contribution terms and an explicit PR acknowledgement.

- [ ] Add contributor terms requiring authority to contribute and granting Cory Davis / NavisWORLD a perpetual, worldwide, irrevocable, royalty-free, sublicensable right to use, modify, commercialize, distribute, and relicense contributions while contributors retain ownership absent separate assignment.
- [ ] Add `CONTRIBUTING.md` stating contributions are accepted only under those terms and explaining third-party code disclosure requirements.
- [ ] Add a pull-request template requiring explicit checkbox acknowledgement of contributor terms and identification of third-party material.

### Task 3: Remove contradictory MIT metadata

**Files:**
- Modify: `README.md`
- Modify: `docs/LICENSING.md`
- Modify: `CORY_DAVIS_IP_AND_ACCESS_NOTICE.md`
- Modify: `pyproject.toml`
- Modify: `sdk/rust/Cargo.toml`

**Interfaces:**
- Consumes: Task 1 legal package.
- Produces: consistent current-version license declarations.

- [ ] Replace README's MIT statement with source-available/commercial dual-licensing summary and links to controlling files.
- [ ] Expand `docs/LICENSING.md` into the repository license map, third-party carve-out, historical MIT boundary, and commercial-license explanation.
- [ ] Align the existing IP/access notice to the new root license and remove language that could conflict with the new limited grant.
- [ ] Replace Python `license = {text = "MIT"}` with custom-license text.
- [ ] Replace Rust `license = "MIT"` with `license-file = "../../LICENSE"`.

### Task 4: Add machine-enforced license audit

**Files:**
- Create: `scripts/license_audit.py`
- Create: `tests/test_license_policy.py`
- Modify: `Makefile`

**Interfaces:**
- Produces: `python3 scripts/license_audit.py` and `make license-audit`.

- [ ] Write unit tests requiring all legal files, custom root license markers, non-MIT package metadata, README/docs custom-license markers, and historical MIT allowlisting.
- [ ] Implement `scripts/license_audit.py` using only the Python standard library. It must return nonzero on missing legal files, contradictory MIT declarations in current-version metadata, or missing custom-license markers.
- [ ] Add `license-audit` to `.PHONY` and `check` in `Makefile` and invoke the script.
- [ ] Run `PYTHONPATH=src:. python3 -m unittest tests.test_license_policy -v`.
- [ ] Run `python3 scripts/license_audit.py`.
- [ ] Run the full `make check` gate in GitHub CI.

### Task 5: Review, verify, and integrate

**Files:**
- Review all changed files on `legal/source-license-v1`.

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: a verified licensing pull request suitable for integration into `main`.

- [ ] Compare branch to `main` and verify no unrelated runtime/OS changes.
- [ ] Open a PR explaining the historical MIT limitation and future source-available boundary.
- [ ] Require GitHub source-validation to pass on the PR head.
- [ ] Merge only after required checks are green.
- [ ] Verify the resulting `main` files expose the new license and no longer identify current Synapse original code as MIT licensed.
