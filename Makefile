PYTHON ?= python3

.PHONY: check test lint cpp rust iso clean

check: test lint cpp rust

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m compileall -q src tests
	$(PYTHON) -m py_compile rootfs/usr/local/bin/synapse-control
	$(PYTHON) -c 'import xml.etree.ElementTree as ET; ET.parse("rootfs/usr/share/icons/hicolor/scalable/apps/synapse-os.svg"); ET.parse("rootfs/usr/share/wallpapers/SynapseOS/contents/images/3840x2160.svg")'
	bash -n build/build.sh build/clean.sh scripts/validate-tree.sh build/hooks/010-synapse.hook.chroot rootfs/usr/local/bin/synapse
	sh -n rootfs/usr/local/lib/synapse/vm-smoke rootfs/usr/local/bin/synflow
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
