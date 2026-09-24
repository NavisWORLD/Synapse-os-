# Synapse OS continuation implementation ledger

Goal: finish the existing Debian 13 / Plasma 6 system against Cory Davis's
2026-09-24 engineering brief. That brief supplies the architecture and authorizes
direct engineering, branch reconciliation, testing and publication. Work proceeds
inline in an isolated continuation branch; no architecture replacement.

## Constraints

- MODEL ≠ MEMORY; MODEL ≠ STATE; MODEL ≠ AUTHORITY.
- Reuse Beast Box; preserve provenance, licenses and checkpoints.
- No physical disk writes, firmware changes, spending increases or public root API.
- Publish only gates actually passed. ARM64, RISC-V and physical targets retain
  their existing unverified/experimental status.

## Recovered source

Original main: `3c0d4d03177eca7410ac4ca0465d4916a12a33c3`.
Branch: `continuation/synapse-beast-awakens-001`.

- PR #18: main already contains the cockpit. Reconciled its seven remaining
  recording commits through a normal merge, retaining original ancestry.
- PR #19: brought forward the independent visual recording workflow by
  cherry-pick, retaining original author and source commit reference here:
  `0598d846847e49933763caf09c51707864c3c7b4`.
- PR #14: source tests already pass on main; its older test-only change is not
  required to repair the current payload gate.
- PR #15 and #16 implement conflicting resident Zeref designs (system service
  versus user service, module versus package). Keep both histories intact while
  selecting and verifying one integration; do not merge both implementations.

## Executable tasks and evidence

- [x] Recover live refs, PRs, workflow logs, release assets and repository rules.
- [x] Reproduce the stale ISO assertion: `runtime exchange` is in the loaded
  conversation module, not in `public/index.html`. Check the actual module link
  and chat endpoint instead. Retain every other payload assertion and add an
  ERR trap so subsequent failures name the exact command.
- [x] Include the existing 36 bridge unit tests in `make check`. Previously
  `unittest discover -s tests` did not recurse into the non-package `tests/unit`.
- [ ] Run `make check`, browser tests, ISO build, live boot and installed cold boot.
- [ ] Extend the existing Beast adapter with a host-owned provider catalog and
  real provider switching; keep the same Beast data directory. Separate provider
  changes from brain identity/permission changes. Add durable execution receipts.
- [ ] Extend Flow's existing capability callbacks with a bounded OS control
  surface. User execution must be explicit; model proposals remain inert.
- [ ] Complete native launchers, real health indicators, desktop accessibility
  modes and phone capability boundaries using existing Plasma/cockpit facilities.
- [ ] Verify optional RAWRPHØS source/checkpoint/tokenizer, run prompt probes and
  A → B → A continuity, record memory, timings, hashes and quality limits.
- [ ] Compare pinned official Omarchy sources; do not infer performance superiority.
- [ ] Review the whole branch, fix critical findings, publish precise evidence
  and release artifacts only after their required gates pass.

## Review focus

1. Provider disconnect must leave durable Beast memory and desktop usable.
2. A provider selection must not grant, revoke or smuggle host authority.
3. Concurrent chat/switch requests must not corrupt the shared persistent store.
4. API requests cannot select executable paths, shell arguments or secret values.
5. Installer evidence must distinguish direct-kernel smoke, UEFI VM boot and
   physical hardware certification.

## Initial verification

Main CI `34300997240`: source and browser jobs passed, ISO built, payload assertion
failed, both VM gates skipped. No new boot success follows from that run.
Local baseline: Python and Node tests, syntax and license checks passed; `make
check` stopped because CMake was absent. CMake/Ninja are installed in the scratch
build environment, not added to the OS dependency contract. Local apt installation
is unavailable due to container UID/setgroups restrictions; real ISO/QEMU work
uses the existing GitHub Actions runner.

The Beast Box source recovered for model integration is
`d6c3fa5b64f847cd98a6d6968d19059a14db3eed`. Its optional 18K package is explicitly
experimental: owner-repetition promotion failed. It must not become the default.
