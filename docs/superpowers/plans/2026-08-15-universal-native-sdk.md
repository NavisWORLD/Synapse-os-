# Synapse Universal Native SDK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stable C ABI and make the C++, Rust, and Python SDKs consume it while installing the native library into every generated Synapse OS image.

**Architecture:** `sdk/c` is the single native ABI source. C++ and Rust link to it; Python loads it through `ctypes` with a pure-Python fallback. The live-build chroot compiles the ABI for the image's target CPU.

**Tech Stack:** C11, CMake, C++17, Rust 2021 FFI, Python 3 `ctypes`, Debian live-build hooks.

## Global Constraints

- ABI version is `1`.
- C ABI has no third-party dependencies.
- Existing C++ `raw_status()` and Python `status()` behavior remains available.
- Status JSON remains opaque text in native code.
- No architecture-specific binary is committed to Git.

---

### Task 1: C ABI

**Files:**
- Create: `sdk/c/include/synapse/synapse.h`
- Create: `sdk/c/src/synapse.c`
- Create: `sdk/c/tests/test_synapse.c`
- Create: `sdk/c/CMakeLists.txt`
- Create: `sdk/c/synapse-abi.pc.in`

**Interfaces:**
- Produces: `synapse_abi_version`, `synapse_result_string`, `synapse_status_read`, `synapse_service_reachable`.

- [ ] Write `test_synapse.c` asserting ABI version 1, two-pass status reading from a temporary file, buffer-too-small behavior, missing-file behavior, and a closed-port probe returning false.
- [ ] Compile the test before implementation with `cc -std=c11 -Isdk/c/include sdk/c/tests/test_synapse.c -o /tmp/synapse-c-red` and verify it fails because the ABI symbols are undefined.
- [ ] Implement the header and source with fixed integer result codes, caller-owned buffers, `getaddrinfo`, nonblocking connect, and `select` timeout handling.
- [ ] Run `cc -std=c11 -Wall -Wextra -pedantic -Isdk/c/include sdk/c/src/synapse.c sdk/c/tests/test_synapse.c -o /tmp/synapse-c-test && /tmp/synapse-c-test` and require exit 0.
- [ ] Add CMake shared/static targets and install rules for the header, library, and pkg-config metadata.

### Task 2: C++ adapter

**Files:**
- Modify: `sdk/cpp/include/synapse.hpp`
- Modify: `sdk/cpp/examples/status.cpp`

**Interfaces:**
- Consumes: ABI v1 C functions.
- Produces: `synapse::raw_status(path)` and `synapse::service_reachable(host, port, timeout_ms)`.

- [ ] Change the C++ example test expectation so it requires the C ABI-backed wrapper and fails before the header is updated.
- [ ] Replace direct file I/O in `synapse.hpp` with two-pass `synapse_status_read` calls and translate ABI failures into `std::runtime_error`.
- [ ] Compile the C source with `cc`, then link the C++ example with `g++ -std=c++17 -Wall -Wextra -pedantic` and the C object.

### Task 3: Rust adapter

**Files:**
- Modify: `sdk/rust/src/lib.rs`
- Modify: `sdk/rust/Cargo.toml`

**Interfaces:**
- Consumes: ABI v1 symbols through private `extern "C"` declarations.
- Produces: safe Rust `raw_status` and `service_reachable`.

- [ ] Add Rust tests that read a temporary status file and verify a closed high port is safe to probe.
- [ ] Run `cargo test --manifest-path sdk/rust/Cargo.toml` without the ABI search path and verify the new FFI test cannot link.
- [ ] Implement private FFI declarations, CString conversion, two-pass buffer allocation, error conversion, and safe wrappers.
- [ ] Build `libsynapse_abi.a` into `/tmp/synapse-rust-check`, then run `RUSTFLAGS='-L native=/tmp/synapse-rust-check' cargo test --manifest-path sdk/rust/Cargo.toml` and require success.

### Task 4: Python adapter

**Files:**
- Modify: `sdk/python/synapse_sdk.py`
- Create: `tests/test_sdk_python.py`

**Interfaces:**
- Consumes: `libsynapse_abi` through `ctypes` when available.
- Preserves: pure Python fallback.

- [ ] Write tests for fallback status reading and for native loading when `SYNAPSE_ABI_LIBRARY` points to a test shared library.
- [ ] Verify the native-loading test fails before the adapter is implemented.
- [ ] Implement library discovery, ctypes signatures, native status/probe calls, and fallback behavior.
- [ ] Build `/tmp/libsynapse_abi.so` and run `PYTHONPATH=sdk/python python3 -m unittest tests.test_sdk_python -v`.

### Task 5: Image integration and repository gate

**Files:**
- Create: `build/hooks/030-native-sdk.hook.chroot`
- Modify: `build/build.sh`
- Modify: `Makefile`
- Modify: `rootfs/usr/local/lib/synapse/vm-smoke`

**Interfaces:**
- Image provides `/usr/lib/libsynapse_abi.so`, `/usr/include/synapse/synapse.h`, and pkg-config metadata.

- [ ] Copy `sdk/c` into the generated chroot source tree from `build/build.sh`.
- [ ] Build/install the ABI in the live-build hook with CMake.
- [ ] Extend VM smoke to verify `libsynapse_abi.so` and compile/run a tiny C consumer.
- [ ] Extend `make check` with C, C++, Rust, and Python SDK gates using the same compiled ABI.
