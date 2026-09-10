from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_full_zeref_payload_is_part_of_generated_rootfs_source():
    required = [
        "rootfs/etc/systemd/system/synapse-zeref.service",
        "rootfs/etc/systemd/system/synapse-zeref-ibm-broker.service",
        "rootfs/etc/systemd/system/synapse-zeref-ibm-broker.timer",
        "rootfs/etc/synapse/zeref.json",
        "rootfs/etc/synapse/zeref-ibm.json",
        "rootfs/usr/local/lib/synapse/zeref-ibm-broker",
        "src/synapse/zeref.py",
        "src/synapse/zeref_service.py",
    ]
    for rel in required:
        assert (ROOT / rel).is_file(), rel


def test_vm_smoke_requires_resident_service_and_fail_soft_status():
    smoke = (ROOT / "rootfs/usr/local/lib/synapse/vm-smoke").read_text(encoding="utf-8")
    assert '"zeref-service"' in smoke
    assert "synapse-zeref.service" in smoke
    assert '"zeref-status"' in smoke
    assert "synapse zeref status" in smoke
    assert "SYNAPSE_VM_READY" in smoke


def test_build_hook_enables_resident_but_not_ibm_timer():
    hook = (ROOT / "build/hooks/010-synapse.hook.chroot").read_text(encoding="utf-8")
    assert "systemctl enable synapse-zeref.service" in hook
    assert "systemctl enable synapse-zeref-ibm-broker.timer" not in hook
