# Synapse Evolution Review Bay — pinned offline import (Stage 3.5)

This is an incremental development feature on top of draft PR #36.
It does not change Synapse production or enable model code execution.

The existing Evolution tab offers **two deliberately distinct modes**:

- **Verify pinned historical evidence (ZIP)**: Open the already-recorded
  owner review artifact from [GitHub Actions run 36189003354](https://github.com/NavisWORLD/Synapse-os-/actions/runs/36189003354),
  artifact `synapse-evolution-owner-review-bundle`. The client hashes all nine
  member files against independent hard-coded SHA-256 pins, parses and checks
  the included SHA256SUMS, rejects extras, duplicates, symlinks and bad ZIP
  members, and compares its *currently installed* debugger source with the
  exact model-assisted, independently reviewed candidate SHA-256.
- **Inspect unverified local receipt (JSON)**: Informational display only.
  Arbitrary JSON is never treated as trusted evidence just because it
  renders convincingly in the UI.

The pinned historical case is intentionally narrow: the genuine Qwen
feedback turn authored only the statement `self.events.clear()`. Its
original proposal was rejected, a separate feedback turn produced the
corrected statement, engineers inserted that statement into a fixed
reviewed source template, and two actual disconnected VM checks followed.
The source change lives in an unmerged development PR. This verifier will
**reject future experiments** until a separately reviewed trust record and
new pins are explicitly introduced; it cannot silently extend trust to
unrelated model claims.

### What successful ZIP verification means

It confirms the bytes match the source-pinned nine-file historical review
artifact and the installed `synapse.debugger` file matches its exact
reviewed candidate. It does **not** establish an independent GitHub digital
signature, fresh CI, current production deployment, malicious-code safety,
model sentience, self-directed OS updates or permission to install. Before
relying on external origin, independently inspect the exact public pinned
Actions run, source commit and downloaded artifact; the local program never
contacts GitHub, accepts credentials or grants operating-system authority.

### Security properties

The import is offline, read-only, bounded to 1 MiB compressed and 400 KiB
uncompressed, rejects archive path surprises and ZIP symlinks, never
extracts files, never interprets proposal code and never writes a receipt
or patch to the running machine. Only the explicit owner can separately
decide whether to advance a draft change following additional testing and
rollback planning. A tested proposal is not automatically a safe release.

Targeted evidence: [pin and native Qt verification CI](https://github.com/NavisWORLD/Synapse-os-/actions/runs/36211761894)
uses the ACTUAL successful historic artifact. It also mutates individual
members and checks that invalid archives fail closed, then opens the genuine
native PyQt Review Bay in an offscreen runner and captures a screenshot.
An offscreen Qt smoke is not a live boot and is never labeled as one.

Full source/browser/ISO/live/installed VM certification for this *new*
development commit is a separate prerequisite before any merge or release.

**MODEL ≠ MEMORY. MODEL ≠ STATE. MODEL ≠ AUTHORITY.**
