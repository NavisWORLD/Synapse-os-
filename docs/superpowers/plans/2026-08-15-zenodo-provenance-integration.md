# Synapse OS Zenodo Provenance Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind the existing Synapse OS licensing package to Cory Davis / NavisWORLD's foundational Zenodo research record without misrepresenting the DOI as a patent, trademark, ownership registration, or replacement for the controlling software license.

**Architecture:** Add a dedicated human-readable provenance record and machine-readable citation file, reference them from the existing legal and public documentation, enforce their presence and DOI through the existing license audit, and embed the provenance files inside every generated Synapse OS image next to the controlling legal package.

**Tech Stack:** Markdown, Citation File Format YAML, Python 3.11 standard library, GNU Make, GitHub Actions, Debian live-build.

## Global Constraints

- Foundational Zenodo DOI: `10.5281/zenodo.17574447`.
- Foundational record title: `The 12-Dimensional Cosmic Synapse Theory: Audio-Driven Deterministic Cosmological Simulation with Adaptive Memory and Light Particle Mapping`.
- Author citation: `C. S. Davis` / Cory Davis.
- Treat the Zenodo DOI as publication and provenance evidence only; do not state that the DOI creates copyright, patent, trademark, or ownership rights.
- Keep `LICENSE` as the controlling license for current Synapse OS Covered Material.
- Do not relicense or claim ownership of third-party components.
- Preserve the historical MIT boundary already recorded in `LICENSE-HISTORY.md`.
- Embed the provenance files in `/usr/share/doc/synapse-os` in generated images.

---

### Task 1: Add canonical provenance and citation files

**Files:**
- Create: `PROVENANCE.md`
- Create: `CITATION.cff`

**Interfaces:**
- Produces: canonical human-readable and machine-readable provenance records consumed by README, NOTICE, licensing docs, build staging, and audit checks.

- [ ] Create `PROVENANCE.md` naming Cory Davis / NavisWORLD, the exact Zenodo title, DOI `10.5281/zenodo.17574447`, and the relationship as foundational research provenance rather than a software-license grant.
- [ ] Add a clear statement that citation does not grant commercial, redistribution, trademark, patent, AI/ML, or other rights beyond the repository's controlling licenses.
- [ ] Create `CITATION.cff` with `cff-version: 1.2.0`, Synapse OS as the software title, Cory Davis as author, the repository URL, the root license name, and the Zenodo record as a preferred related identifier/reference rather than falsely assigning the Zenodo DOI to Synapse OS itself.

### Task 2: Link provenance into the legal/public package

**Files:**
- Modify: `NOTICE`
- Modify: `LICENSE-HISTORY.md`
- Modify: `COMMERCIAL-LICENSING.md`
- Modify: `README.md`
- Modify: `docs/LICENSING.md`
- Modify: `CORY_DAVIS_IP_AND_ACCESS_NOTICE.md`

**Interfaces:**
- Consumes: `PROVENANCE.md`, `CITATION.cff`.
- Produces: consistent public provenance references without changing the controlling scope of `LICENSE`.

- [ ] Add `PROVENANCE.md` and `CITATION.cff` references to `NOTICE` and identify the Zenodo DOI as foundational research provenance.
- [ ] Add a `Research provenance` section to `LICENSE-HISTORY.md` separating the research publication timeline from the software license timeline.
- [ ] Add a provenance paragraph to `COMMERCIAL-LICENSING.md` stating citation/publication does not grant commercialization permission.
- [ ] Add a concise `Research provenance` section to README with the exact DOI and link to `PROVENANCE.md`.
- [ ] Add a provenance section to `docs/LICENSING.md` explaining that publication provenance and software licensing are distinct.
- [ ] Add the DOI and provenance-file links to `CORY_DAVIS_IP_AND_ACCESS_NOTICE.md` without claiming the DOI creates exclusive rights.

### Task 3: Enforce DOI provenance in audit/tests

**Files:**
- Modify: `scripts/license_audit.py`
- Modify: `tests/test_license_policy.py`

**Interfaces:**
- Produces: fail-closed validation requiring `PROVENANCE.md`, `CITATION.cff`, and the exact DOI in the canonical provenance surfaces.

- [ ] Add `PROVENANCE.md` and `CITATION.cff` to `REQUIRED_FILES`.
- [ ] Add DOI marker `10.5281/zenodo.17574447` to required provenance checks.
- [ ] Require README, NOTICE, and `docs/LICENSING.md` to reference `PROVENANCE.md` and the DOI.
- [ ] Extend unit tests to verify the DOI exists in both provenance files and that `PROVENANCE.md` explicitly distinguishes provenance from license/ownership registration.
- [ ] Preserve the existing permissive-license drift audit behavior.

### Task 4: Embed provenance in bootable images and CI inspection

**Files:**
- Modify: `build/build.sh`
- Modify: `.github/workflows/build-vm-smoke.yml`
- Modify: `tests/test_license_policy.py`

**Interfaces:**
- Consumes: `PROVENANCE.md`, `CITATION.cff`.
- Produces: generated images containing both provenance records under `/usr/share/doc/synapse-os`.

- [ ] Add `PROVENANCE.md` and `CITATION.cff` to the legal/provenance staging loop in `build/build.sh`.
- [ ] Add both files to live-filesystem extraction and presence checks in `build-vm-smoke.yml`.
- [ ] Add a CI grep requiring the DOI inside the embedded `PROVENANCE.md`.
- [ ] Update the image-staging unit test to require both files.

### Task 5: Verify and integrate

**Files:**
- Review all changes on `legal/zenodo-provenance`.

**Interfaces:**
- Produces: a clean provenance-only PR on top of the existing Synapse Source License migration.

- [ ] Run/require `make check` so the license audit, unit tests, C/C++/Rust/Python gates, and architecture checks remain green.
- [ ] Run/require the amd64 ISO build, filesystem inspection, checksum, and QEMU boot gate.
- [ ] Open a PR that states the DOI is evidence of research publication/provenance, not a substitute for copyright registration, patent rights, trademark registration, or the controlling software license.
- [ ] Merge only after the required GitHub Actions workflow passes on the PR head.
- [ ] Confirm `main` contains `PROVENANCE.md`, `CITATION.cff`, and DOI `10.5281/zenodo.17574447` after merge.
