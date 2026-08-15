# Synapse Universal Native SDK Design

## Goal

Create one stable native interoperability boundary for Synapse OS so C, C++, Rust, Python, and future language adapters can consume the same status and service-probe behavior without reimplementing OS contracts independently.

## Core ABI

The center is a versioned C ABI in `sdk/c/` with no third-party dependencies. ABI v1 exposes:

- `synapse_abi_version()`
- `synapse_result_string()`
- `synapse_status_read()` with a query-size-then-read contract
- `synapse_service_reachable()` with an explicit timeout

The ABI uses integer result codes, fixed-width integer arguments, caller-owned buffers, and `extern "C"` declarations so it remains consumable from C++, Rust FFI, Python `ctypes`, Swift, Kotlin/Native, Go cgo, C#, and other FFI systems later.

## Language adapters

### C

C is the canonical ABI and ships a header, shared/static-library CMake target, and smoke test.

### C++

The existing header becomes a zero-overhead RAII wrapper over the C ABI. It returns `std::string`, converts ABI errors into `std::runtime_error`, and preserves the existing `raw_status()` entrypoint.

### Rust

The Rust crate exposes safe `raw_status()` and `service_reachable()` functions backed by the C ABI. The repo test target builds the C ABI first and links the Rust tests to it. The unsafe FFI declarations remain private.

### Python

The Python SDK loads `libsynapse_abi` with `ctypes` when available and retains a pure-Python fallback so developer machines can still use the SDK before the native library is installed.

## OS image integration

The live image compiles the C ABI inside the target chroot, installs `libsynapse_abi.so`, the public header, and a pkg-config file. This avoids committing architecture-specific binaries while ensuring each generated image contains a native library built for its own CPU architecture.

## Compatibility rules

- ABI v1 symbols are additive only.
- Existing function signatures cannot change within ABI v1.
- Caller memory ownership is explicit.
- No JSON parser dependency is added to the C ABI; status JSON remains opaque text.
- Networking is IPv4/IPv6 hostname-capable through `getaddrinfo`.
- The native SDK must compile with C11 and C++17.

## Verification

`make check` must compile and execute the C smoke test, compile/link the C++ example against the C ABI, run Rust tests against the same ABI library, and run Python SDK tests with both native and fallback paths.
