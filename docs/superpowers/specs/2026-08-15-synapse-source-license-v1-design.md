# Synapse Source License v1 Protection Package Design

## Purpose

Replace the repository's future-facing MIT licensing with a source-visible, permission-gated dual-license structure that preserves Cory Davis / NavisWORLD's control over original Synapse OS material while accurately preserving third-party licenses and historical MIT grants.

This design is intended to improve practical IP control and provenance. It is not a substitute for advice from a licensed attorney, and it does not claim that any software license can make copying, infringement, or misuse impossible.

## Legal boundaries the repository must state accurately

1. Versions already distributed under MIT remain subject to the MIT grant that accompanied those versions. The new license applies to repository revisions whose root `LICENSE` contains Synapse Source License v1.0 and to later original Synapse material unless a file states otherwise.
2. Copyright protects copyrightable code, documentation, artwork, and other original expression. It does not by itself protect abstract ideas, algorithms, systems, methods, processes, or discoveries.
3. Debian, Linux, libraries, tools, firmware, fonts, packages, and other third-party components remain governed by their own licenses. The Synapse license cannot relicense those components.
4. Source-visible restrictions on commercial use, fields of endeavor, redistribution, or AI use mean the project must not describe this license as OSI-approved "open source."
5. No claim of registered trademark or patent rights will be made unless registration or issued rights are independently verified.

## Licensing model

### Public license: Cory Davis / NavisWORLD Synapse Source License v1.0

The public license will grant a narrow, non-exclusive, non-transferable right to:

- inspect the source;
- make a local copy for personal, noncommercial evaluation;
- run the Software privately for personal, noncommercial evaluation, research, education, interoperability testing, and security review;
- make private local modifications only for those permitted evaluation purposes;
- submit feedback, bug reports, and proposed contributions to the Licensor.

The public license will not grant permission to deploy the Software in production or for an organization without separate written authorization.

### Permission-required activities

A separate written permission or commercial agreement from Cory Davis / NavisWORLD will be required for any of the following involving original Synapse material:

- commercial use or activity intended to generate revenue or business advantage;
- enterprise, institutional, government, or organizational production deployment;
- sale, resale, rental, lease, OEM bundling, paid support bundling, or monetized distribution;
- redistribution of source or binaries, public mirrors, repackaging, sublicensing, or publication of modified versions;
- hosted, cloud, SaaS, API, managed-service, or multi-user service offerings;
- embedding Synapse into another product, appliance, operating-system distribution, SDK, platform, or commercial workflow;
- distributing derivative works or ports;
- using protected Synapse source, documentation, architecture material, or extracted corpora to train, fine-tune, distill, benchmark for model development, create embeddings for model development, create training datasets, or otherwise develop or improve a machine-learning model;
- removing, obscuring, or replacing copyright, provenance, licensing, or attribution notices;
- using Synapse OS, NavisWORLD, COSMOS, or other Licensor branding in a way that implies sponsorship, origin, endorsement, or affiliation without permission;
- granting downstream rights to another party.

The license will make clear that permission for one activity does not imply permission for another.

## Rights reserved

The package will expressly reserve all rights not granted, including:

- copyright rights in original Synapse code, documentation, graphics, architecture descriptions, and other protectable expression;
- any patent rights that may exist now or in the future, with no patent license granted by the public source license;
- trademark, trade name, logo, and branding rights to the extent owned or claimed by the Licensor;
- trade-secret rights in material that has not been publicly disclosed;
- commercial licensing, relicensing, sublicensing, and enforcement rights.

The public license will include a patent-litigation termination provision for rights granted under the source license.

## Historical MIT boundary

The repository will add `LICENSE-HISTORY.md` explaining that earlier revisions were publicly released under MIT and that the new source license does not purport to revoke permissions already granted for those historical copies.

The historical MIT text will be preserved in `licenses/MIT-HISTORICAL.txt` for provenance. It will not remain the active root license.

This avoids a false claim that the historical repository was never MIT-licensed.

## Repository files

The implementation will create or update:

- `LICENSE` as the active Synapse Source License v1.0;
- `LICENSE-HISTORY.md` for the MIT-to-source-license provenance boundary;
- `COMMERCIAL-LICENSE.md` explaining activities that require direct permission and how to request it;
- `NOTICE` with ownership, provenance, third-party, and no-implied-license notices;
- `TRADEMARKS.md` reserving brand rights without claiming federal registration unless verified;
- `CONTRIBUTOR-LICENSE-AGREEMENT.md` granting Cory Davis / NavisWORLD broad rights to use, modify, relicense, sublicense, distribute, and commercialize accepted contributions, plus an appropriate contributor patent grant;
- `CONTRIBUTING.md` requiring contributors to affirm the contributor agreement before submission;
- `.github/pull_request_template.md` with an explicit CLA/provenance affirmation checkbox;
- `docs/LICENSING.md` explaining active license scope and third-party carve-outs;
- `README.md` replacing the MIT statement with a concise source-license notice;
- `SECURITY.md` only if existing language conflicts with the new licensing rules;
- source-file license headers where practical for original Synapse SDK/core files, using a short SPDX-style custom identifier plus copyright notice rather than duplicating the full license in every file.

## Third-party boundary

The package will not claim ownership over Debian, the Linux kernel, system packages, QEMU, Rust/C/C++ runtimes, Python, third-party dependencies, or other externally authored components.

`docs/LICENSING.md` and `NOTICE` will state that generated Synapse OS images are aggregations containing components under independent licenses and that users must preserve those notices and satisfy the applicable third-party terms.

If a third-party file already contains a license header, that header will not be overwritten with the Synapse license.

## Contributor control

New external contributions create relicensing risk if ownership and permissions are ambiguous. The repository will therefore require contributors to affirm that:

- they have the right to submit the contribution;
- their contribution is original or properly identified as third-party material;
- they grant Cory Davis / NavisWORLD a perpetual, worldwide, irrevocable copyright license to use, reproduce, modify, distribute, sublicense, relicense, and commercialize the contribution;
- they grant an appropriate patent license for patent claims necessarily infringed by their contribution;
- they understand the project may distribute their contribution under the Synapse Source License, a commercial license, or another license selected by the Licensor.

The repository will note that a dedicated signed/e-sign CLA workflow reviewed by counsel provides stronger operational evidence than a repository checkbox alone.

## Brand control

The project will reserve permission to use project names, logos, trade dress, or confusingly similar branding in redistributed products or services. It will use `TM` only where appropriate and will not use the federal registration symbol `®` unless registration is verified.

No source-code permission will automatically include trademark permission.

## Enforcement and termination

The source license will provide that:

- rights terminate automatically upon material breach;
- a breaching party must stop use and distribution of protected Synapse material;
- termination does not limit remedies otherwise available to the Licensor;
- warranty is disclaimed and liability is limited to the maximum extent permitted by applicable law;
- no waiver is created by delayed enforcement;
- if one provision is unenforceable, the remainder survives to the extent permitted by law.

A state-specific governing-law or venue clause will not be invented without verified owner/legal information. Separate commercial agreements can specify governing law, venue, fees, indemnity, audit rights, support obligations, and negotiated commercial terms.

## Verification

Before merge, the licensing branch will be checked for:

- remaining claims that original Synapse code is currently MIT-licensed;
- contradictory "open source" language;
- accidental relicensing of third-party material;
- missing license links in README/docs;
- missing contributor affirmation;
- references to unverified registered trademarks or patents;
- malformed custom license identifiers;
- source/build tests to ensure licensing changes do not break the OS build.

The final pull request will summarize the historical MIT limitation and clearly identify what the new license can and cannot accomplish.
