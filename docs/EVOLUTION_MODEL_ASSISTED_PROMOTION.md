# Reviewed candidate: model-assisted opt-in debugger trace reset

**Development proposal only. Not merged or released.** This branch promotes the
exact previously staged candidate into the *source of a separate draft PR* so
normal full source validation, browser regression, ISO build, boot and
installation gates can run before any owner-controlled merge decision.

## Reproducible model provenance

- An independent CPU run of a revision-pinned public coder model originally
  proposed replacing the debugger's event list; exact reviewer rejected it,
  correctly, because other references would stop sharing the original list.
  Original [model run](https://github.com/NavisWORLD/Synapse-os-/actions/runs/36150437142).
- The same immutable model revision was then given the exact rejection
  feedback. It genuinely returned an in-place clear statement wrapped in one
  Markdown code fence:
  `self.events.clear()`
  Feedback [run](https://github.com/NavisWORLD/Synapse-os-/actions/runs/36150869207).
- Pinned model: Qwen/Qwen2.5-Coder-0.5B-Instruct, revision
  ea99d3edbfc6669b8b24cbaa6a98ec0e857f0155.
  Feedback raw response SHA-256:
  8723342b9531a7ae1e13d1ade26b8bdaec17aa5bb10f3776235fb554fa477fa1.
- The model authored **that statement only**; an explicitly documented
  trusted template supplies the optional keyword-only method argument and
  conditional. Do not attribute the complete patch, tests or experiment
  harness to the model.

## Actual independent virtual-machine evidence

The [two-VM workflow](https://github.com/NavisWORLD/Synapse-os-/actions/runs/36151721750)
archived its real guest evaluation artifact:
`synapse-real-model-corrected-two-vm-evidence`.

Its `COMPARISON.json` reports separate QEMU TCG baseline and candidate
boots, both without a NIC, with read-only boot and payload media.
Both guests passed the same independent status, doctor and debugger default
regressions. Only the patched guest additionally exercised and passed the
explicit in-place reset. The candidate was not executed on the GitHub host.
The raw previous rejection, exact corrected output and the cryptographic
source/patch evidence are retained in the artifact.

This is a bounded functional result, **not a measured performance improvement
or comprehensive isolation proof**. The source copy remains a draft, and
this branch must pass its own native/SDK/browser/ISO/boot/install checks.

## Precise source behavior

Before, `Debugger.run()` accumulated trace events across calls and returned
its shared `events` list.

After, the same default is preserved. The explicitly requested
`Debugger.run(reset_events=True)` clears **the same existing list** *before*
starting the next run. This preserves references to the trace list and does
not modify authority or access to debugger modules or other model state.

The independent source regression suite covers original list identity,
cumulative defaults, keyword-only opt-in behavior, breakpoints, capability
identity and source-event immutability. No generated tests are treated as
independent proof.

## Explicit release boundary

This branch does **not** auto-merge PRs, deploy a website, install on real
hardware, grant an AI tools, move credentials, copy private memory, enable
unattended updates or change any existing stable release.

Review the real model artifacts, pinned source diff, and full candidate CI
before considering a merge. Release promotion remains a separate explicit
owner-controlled decision with backups and rollback verification.

MODEL != MEMORY. MODEL != STATE. MODEL != AUTHORITY.
