# Real model self-improvement trial 015 → independent VM trial 016

Owner: Cory Davis / NavisWORLD. Experimental, draft-only, no owner
credentials, no paid cloud inference and no unattended production updates.

## Real model generation: actual evidence, not a scripted response

Independent GitHub Actions run [36213993540](https://github.com/NavisWORLD/Synapse-os-/actions/runs/36213993540)
used the actual public Qwen/Qwen2.5-Coder-0.5B-Instruct CPU model, revision
ea99d3edbfc6669b8b24cbaa6a98ec0e857f0155. Real model generation
completed and the CI artifact retains both exact replies. The prompt
requested a single line of Python that creates a list of shallow independent
copies of existing trace event dictionaries.

Turn 1 was rejected: the model proposed the wrong dictionary-copy expression.
A second, separately recorded real model turn received specific validator
feedback. Turn 2 returned the accepted one-line statement:

    return [event.copy() for event in self.events]

That is the **entire model-authored code scope**. The trusted engineering
template adds a separate snapshot_events method and its signature/docstring.
The prior model-assisted reset_events implementation remains unchanged.
Neither the model nor the template wrote security policy, altered the running
Synapse image or claimed to have run tests. An accepted Stage 1 patch only
establishes syntax and source/hash integrity.

## Bind genuinely generated code into a new clean development branch

Branch 016 uses a distinct offline verifier which downloads the original
actual model artifact from exact run 36213993540. Its independent source pins
cover TRIAL_VERDICT.json, both real model messages and the real staged patch.
The first rejected response must remain rejected. The exact accepted
model statement is reassembled through the original trusted template against
the independently pinned debugger baseline. Any byte/identity mismatch
fails before any candidate is accepted for VM testing.

This verifier re-stages into a detached local review checkout with current
branch source HEAD and emits a new receipt. Neither the raw model response
nor an artifact filename is treated as permission to deploy or to execute on
the GitHub host.

The independent verifier [passed](https://github.com/NavisWORLD/Synapse-os-/actions/runs/36214259874)
with tests of both baseline and candidate regression contracts. Those
non-VM tests **do not** establish that the new VM experiment passes.

## Separate actual VM verification gate

The new branch adds a trusted regression to the root-owned QEMU-only guest
evaluator. The prior reviewed Debugger.run(reset_events=True) contract is
required on BOTH baseline and candidate; the new snapshot_events method is
required ONLY on candidate. The fixed tests ensure the returned list and
top-level dictionaries are distinct from the original, and modifying the
snapshot cannot mutate the stored event records at the tested top level.

After building an entirely NEW Synapse amd64 ISO, the independent host-side
evaluator verifies that actual image, checks its trusted guest evaluator and
baseline source contents, mounts only a read-only, SHA-bound candidate payload,
and boots two separate QEMU TCG guests without any NIC or host source/secret
mounts. Both run fixed status/doctor checks and the trusted debugger contract.
Raw model replies are preserved as evidence; model-generated tests are NOT
used as the independent acceptance standard.

A successful full build and recorded baseline+candidate guest receipts are
needed before reporting the new feature as VM-tested. Any failed result must
stay visible. The experiment is functional smoke testing, not proof of strong
malware containment, deep immutable snapshots, superior performance or
generalized whole-OS autonomous evolution.

## Production and memory boundary

The model gets neither root nor arbitrary shell/OS authority. Its output is
rejected unless it passes precise source and independent behavioral gates.
The candidate exists only in a disposable VM and detached Git checkout.
No merge, release, installer, cloud deployment, OTA update or transfer of
Beast/COSMOS memory is performed. Separately authorize any later PR
promotion and preserve rollback to the original reviewed debugger source.

MODEL != MEMORY. MODEL != STATE. MODEL != AUTHORITY.
