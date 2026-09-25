# Stage 2 — disconnected Evolution VM evaluator (experiment)

Owner: Cory Davis / NavisWORLD. This is a DRAFT experiment layered on top
of Stage 1's reviewed source staging. It does NOT deploy, merge or authorize
any candidate patch. It cannot certify malicious arbitrary code as safe.

## What the two-guest test measures

Given a Stage 1 detached source checkout and original per-file hashes, the
host evaluator checks the exact selected source HEAD, checks the complete
review patch digest, verifies the candidate files and bounds, and compares
them with the original bytes compiled into a PINNED Synapse amd64 ISO.

The host then creates a tiny READ-ONLY candidate payload ISO and boots that
Synapse image twice, from fresh QEMU TCG processes. The first guest performs
the unchanged baseline checks. The second copies the same first-party
package into disposable guest RAM, applies only the receipt-matched candidate
files and performs the same fixed checks:

- Python syntax compilation of the complete scratch package.
- The actual Synapse control CLI, run as non-root with a cleared environment:
  'synapse --json status' and 'synapse doctor'.
- Original file SHA-256 versus the pinned Synapse image, replacement SHA-256
  versus the reviewed Stage 1 receipt.

No model-proposed tests are counted as independent evidence. The first CI
trial uses a deterministic core.py marker addition with zero external model
inference; it does not imply RAWRPHØS or any cloud model generated that patch.

## Explicit QEMU and authority gates

- QEMU command is fixed, TCG only, two vCPUs and 4 GiB guest RAM.
- Networking is disabled at the QEMU device layer ('-nic none').
- The verified boot ISO and generated payload ISO are read-only.
- The evaluator passes no host filesystem sharing, credentials, memory
  directory, model weights, authority ledger, QMP or shell command.
- Separate guest boots have a bounded timeout and emit short JSON receipts
  over serial. Child process stdout/stderr is captured and discarded.
- The trusted guest script exists only in the development image and its
  systemd unit runs ONLY on live media explicitly booted with
  'synapse.evolve_vm=1' and a valid baseline/candidate role.
- The actual source repo, installed Synapse OS and Beast continuity volume
  are never mounted inside the disposable guest. Release keys, real user
  data and model credentials are deliberately absent.

The guest's isolated user still runs Python from an experimental proposal.
Network disconnection and QEMU isolation substantially constrain what the
test can access, but they are not a mathematically complete security
boundary. QEMU and kernel vulnerabilities, resource exhaustion and semantic
malicious behavior need separate security reviews.

The experiment compares functional smoke checks only. Any reported durations
are observations from individual virtual machines and are NOT performance
benchmarks or grounds for an unattended system update.

## Actual CI gate

PR #32 adds a branch-conditional step to the EXISTING full amd64 build:
after building/verifying/booting the Synapse image, generate a deterministic
test patch in a separate Stage 1 checkout, run host-side receipt validation,
launch the two disconnected guests, compare fixed results, then archive
COMPARISON.json, guest serial, original receipt and review patch. The
existing installed-system smoke test and normal asset preservation follow.

The workflow must finish successfully before treating the two VM boots
and their functional checks as demonstrated. A syntactically correct workflow,
unit-test pass or green first boot does not establish two completed runs.

Do not use this mechanism to execute patches from untrusted public PRs,
billed providers or unreviewed model outputs on production. Before scaling,
move the trusted evaluator onto a dedicated restricted runner, pin and verify
QEMU/kernel package versions, impose host resource isolation, review model
source disclosure and require explicit owner approval for any promotion.

Next milestone: connect the Stage 1.5 local Beast model adapter to this
evaluation gate through a signed, owner-approved staging artifact and then
show repeatable independent model-generated improvement measurements.
Model-origin attestation, prompt retention and continuity safety remain
separate from smoke-test results.

MODEL != MEMORY. MODEL != STATE. MODEL != AUTHORITY.
