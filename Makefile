PYTHON ?= python3
ABI_BUILD ?= /tmp/synapse-abi-check

.PHONY: check test lint license-audit c cpp rust python-sdk arch-config iso clean

check: test lint license-audit c cpp rust python-sdk arch-config

test:
	PYTHONPATH=src:. $(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m compileall -q src tests scripts
	$(PYTHON) -m py_compile rootfs/usr/local/bin/synapse-control
	$(PYTHON) -c 'import xml.etree.ElementTree as ET; ET.parse("rootfs/usr/share/icons/hicolor/scalable/apps/synapse-os.svg"); ET.parse("rootfs/usr/share/wallpapers/SynapseOS/contents/images/3840x2160.svg")'
	bash -n build/build.sh build/clean.sh scripts/validate-tree.sh scripts/qemu-smoke.sh
	sh -n build/hooks/010-synapse.hook.chroot build/hooks/020-phone-bootstrap.hook.chroot build/hooks/030-native-sdk.hook.chroot rootfs/usr/local/bin/synapse rootfs/usr/local/bin/synapse-phone-bootstrap rootfs/usr/local/bin/synapse-genesis-writer rootfs/usr/local/lib/synapse/vm-smoke rootfs/usr/local/bin/synflow
	./scripts/validate-tree.sh

license-audit:
	$(PYTHON) scripts/license_audit.py

c:
	rm -rf $(ABI_BUILD)
	cmake -S sdk/c -B $(ABI_BUILD) -G Ninja -DCMAKE_BUILD_TYPE=Release
	cmake --build $(ABI_BUILD)
	ctest --test-dir $(ABI_BUILD) --output-on-failure

cpp: c
	mkdir -p /tmp/synapse-cpp-check
	printf '%s\n' '{"sdk":"cpp"}' > /tmp/synapse-cpp-check/status.json
	g++ -std=c++17 -Wall -Wextra -pedantic -Isdk/c/include -Isdk/cpp/include sdk/cpp/examples/status.cpp -L$(ABI_BUILD) -lsynapse_abi -Wl,-rpath,$(ABI_BUILD) -o /tmp/synapse-cpp-check/status
	/tmp/synapse-cpp-check/status /tmp/synapse-cpp-check/status.json

rust: c
	@if command -v cargo >/dev/null 2>&1; then LD_LIBRARY_PATH=$(ABI_BUILD):$${LD_LIBRARY_PATH:-} RUSTFLAGS='-L native=$(ABI_BUILD)' cargo test --manifest-path sdk/rust/Cargo.toml; else echo "cargo not installed; Rust execution gate skipped locally (CI installs Rust)"; fi

python-sdk: c
	SYNAPSE_ABI_LIBRARY=$(ABI_BUILD)/libsynapse_abi.so PYTHONPATH=sdk/python $(PYTHON) -m unittest discover -s tests -p 'test_sdk_python.py' -v

arch-config:
	$(PYTHON) scripts/arch_matrix.py validate
	SYNAPSE_DRY_RUN=1 SYNAPSE_ARCH=amd64 ./build/build.sh
	SYNAPSE_DRY_RUN=1 SYNAPSE_ARCH=arm64 ./build/build.sh
	SYNAPSE_DRY_RUN=1 SYNAPSE_ARCH=riscv64 ./build/build.sh
	SYNAPSE_QEMU_DRY_RUN=1 bash scripts/qemu-smoke.sh amd64 /tmp/not-used.iso
	SYNAPSE_QEMU_DRY_RUN=1 bash scripts/qemu-smoke.sh arm64 /tmp/not-used.iso
	SYNAPSE_QEMU_DRY_RUN=1 bash scripts/qemu-smoke.sh riscv64 /tmp/not-used.iso

iso:
	sudo ./build/build.sh

clean:
	sudo ./build/clean.sh
