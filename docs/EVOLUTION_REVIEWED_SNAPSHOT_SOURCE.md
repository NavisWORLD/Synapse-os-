# Reviewed candidate: verified model-assisted debugger trace snapshot

**Development-only draft. No merge, production change, release, or delegated authority.**
This proposal places the already two-VM-verified shallow debugger snapshot
candidate into a distinct reviewable source branch. It does not attribute
the full implementation or tests to an AI model.

## Model-origin scope and independent trial

A real pinned CPU model (Qwen/Qwen2.5-Coder-0.5B-Instruct, immutable revision
ea99d3edbfc6669b8b24cbaa6a98ec0e857f0155) generated a first answer that
was rejected by the fixed validator. After one feedback turn, the genuine raw
model response was exactly:

    return [event.copy() for event in self.events]

**Only that one statement was model-authored.** A reviewed fixed template
supplied the snapshot_events() method signature and docstring. Independent,
non-model-authored regression tests and offline VM evaluation determined whether
the assembled candidate worked. Original model generation:
[GitHub run 36213993540](https://github.com/NavisWORLD/Synapse-os-/actions/runs/36213993540).

The immutable historical output and diff were independently rebound and tested
in two separate disconnected QEMU guests using a newly built Synapse OS ISO.
Both guests passed fixed status, doctor and debugger behavior checks. The
candidate additionally passed shallow snapshot-specific functional checks;
there was no model-authorized shell, secret, memory or host source access.
[Two-VM evidence run 36214364431](https://github.com/NavisWORLD/Synapse-os-/actions/runs/36214364431),
artifact synapse-real-model-snapshot-two-vm-evidence.

This branch proposes **the exact reviewed source addition**, not a new
inference run. Independent source regressions cover empty snapshots,
independent top-level list/dict copies, cumulative trace behavior, existing
in-place reset, breakpoint annotation and explicit **shallow** semantics.
Nested objects still share references; neither deep immutability nor
security containment is claimed.

## Separate RAWRPHØS result

Do not misattribute this Qwen-authored statement to RAWRPHØS. The separate
native RAWRPHØS **12K** CPU probe
[run 36218415774](https://github.com/NavisWORLD/Synapse-os-/actions/runs/36218415774)
loaded the pinned 12K checkpoint but generated *no accepted Python statement*
in two bounded prompts. Its rejected turns and verdict remain in artifact
synapse-genuine-rawrphos-cpu-proposal-017.
RAWRPHØS source contribution and corresponding two-VM trial remain **NOT RUN**.
This is a capability gap to address in later model training/evaluation, not
permission to substitute a fixture or claim the other model's success.

## Owner review boundary

The reviewed source candidate is not automatically promoted by CI checks.
Compare the proposed source diff with immutable historical VM evidence and
review new source/SDK/browser/boot checks before considering a merge. Keep
stable alpha and production unchanged until a separately authorized release.

MODEL != MEMORY. MODEL != STATE. MODEL != AUTHORITY.
