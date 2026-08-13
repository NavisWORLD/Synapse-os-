PYTHON ?= python3

.PHONY: check test lint cpp rust iso clean

check: test lint cpp rust

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m compileall -q src tests
	bash -n build/build.sh build/clean.sh scripts/validate-tree.sh build/hooks/010-synapse.hook.chroot rootfs/usr/local/bin/synapse
	./scripts/validate-tree.sh

cpp:
	mkdir -p /tmp/synapse-cpp-check
	g++ -std=c++17 -Wall -Wextra -pedantic -Isdk/cpp/include sdk/cpp/examples/status.cpp -o /tmp/synapse-cpp-check/status

# Rust validation is opportunistic locally; run it anywhere Cargo is available.
rust:
	@if command -v cargo >/dev/null 2>&1; then cargo check --manifest-path sdk/rust/Cargo.toml; else echo "cargo not installed; Rust check skipped in this environment"; fi

iso:
	sudo ./build/build.sh

clean:
	sudo ./build/clean.sh
