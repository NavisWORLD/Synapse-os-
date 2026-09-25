# Real model feedback → bounded code change → independent Synapse VM gate

**Experiment, not a release.** Owner: Cory Davis / NavisWORLD.

This extends the existing draft Evolution Engine without replacing Beast Box,
updating the installed OS, merging PRs, transferring authority or using paid
model inference. Previous experiments established model-authored *prose*
staged and tested in two disconnected guest VMs. This experiment targets a
small, real, opt-in **behavioral change**.

## Independently recorded model attempts

1. In a genuine public CPU inference, SmolLM2-135M-Instruct failed to
   produce the one requested Python statement. The output remains recorded
   as an explicitly rejected trial (GitHub run 36149933563).
2. Qwen2.5-Coder-0.5B-Instruct, pinned to immutable public snapshot
   ea99d3edbfc6669b8b24cbaa6a98ec0e857f0155, genuinely responded to
   the initial single-line task, but suggested assigning a new empty list.
   That would violate the requirement to preserve the original event-list
   identity, so the exact-match reviewer rejected it. Historical model
   trial: GitHub Actions 36150437142.
3. A separate genuine CPU run retrieved **that exact earlier result** by
   immutable GitHub Actions run ID and verified its bytes and SHA-256.
   We supplied the model explicit rejection feedback explaining the
   list-identity bug. Its new, actual reply contained the correct in-place
   clearing call. The reviewer removed only an optional single Markdown
   code-fence wrapper, strictly checked the resulting statement, and
   assembled a known bounded opt-in method signature. This is
   feedback-guided model assistance, NOT a claim the model authored all
   the surrounding code. Corrected trial: GitHub Actions 36150869207.

The model-bound Stage 1 review patch changes only Debugger.run:
the optional keyword-only reset_events flag defaults to False, so
existing calls retain cumulative event history. When explicitly True,
the method clears the same list instance before recording new events.
The model authored one line; the surrounding conditional and signature
came from a fixed trusted template.

For faithful provenance, inspect these exact files in the corrected
trial artifact: VERIFIED_PREVIOUS_REPLY.txt, ACTUAL_FEEDBACK_REPLY.txt,
RESULT.json, MODEL_BOUND_PROPOSAL.json, PATCH_REVIEW.diff and RECEIPT.json.

## Stage 2 independent evaluation

This separate branch downloads the exact original corrected-trial artifact,
rechecks both raw model replies and SHA-256, compares the original source bytes
and reconstructed patch byte-for-byte with that artifact, then re-stages the
same change against a fresh clean Git HEAD. It refuses missing, forged or
modified evidence. The narrow preflight GitHub Actions run
36151563530 passed. The production source remains unchanged.

The branch also adds a trusted *fixed* debugger regression to the prior
Stage 2 guest evaluator. Both baseline and candidate guest runs must pass
the existing system status and doctor checks. Both independently check that
ordinary Debugger.run continues to accumulate history, returns the same
list object, preserves breakpoint marking and never mutates the original
trace event. Only the candidate guest is additionally expected to accept
reset_events=True and clear the existing list in place.

The QEMU runner verifies the entire new Synapse ISO checksum and ensures the
trusted guest evaluator and original debugger.py bytes in the ISO match this
source. It boots one baseline and one candidate guest using TCG, with NO QEMU
network device, read-only image/payload media, no owner credentials, no
mounted Beast memory or host source tree, non-root bounded smoke subprocesses
and retained JSON/serial evidence. The real model-generated statement is
not run on the GitHub host, and model-authored tests are not accepted.

**The full ISO/two-VM verification has to complete before calling the
new behavior experimentally verified.** Source syntax, prior model runs,
a verified Stage 1 review patch or green preflight alone cannot establish
the result.

## Non-claims

This is a narrow, feedback-guided software change, not independent
whole-OS self-development, a measured performance improvement, a security
proof, consciousness or physical-quantum evidence. Two QEMU boots do not
establish physical hardware reliability. The public model's Git revision
and real Actions transcript bind the declared experiment; an unverified
model label inside a JSON proposal by itself is not model-origin attestation.
No merged release, auto-update, automated privileges or production change is
authorized by this experiment.

**MODEL != MEMORY. MODEL != STATE. MODEL != AUTHORITY.**

Next independent stages are owner review, an opt-in approved draft source PR
for the exact measured patch, broader regression coverage, resource/rollback
checks, and only then separate release acceptance.
