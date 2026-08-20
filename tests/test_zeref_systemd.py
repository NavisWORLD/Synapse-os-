from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEMD = ROOT / "rootfs/etc/systemd/system"


def text(name: str) -> str:
    return (SYSTEMD / name).read_text(encoding="utf-8")


def test_model_service_has_no_ibm_credential_and_no_network():
    unit = text("synapse-zeref.service")
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "ProtectHome=true" in unit
    assert "PrivateNetwork=true" in unit
    assert "LoadCredential=" not in unit
    assert "IBM_QUANTUM_TOKEN" not in unit
    assert "InaccessiblePaths=/etc/synapse/credentials /run/credentials" in unit
    assert "ReadWritePaths=/run/synapse/zeref /var/lib/synapse/zeref" in unit


def test_broker_is_credential_isolated_and_never_auto_submits():
    unit = text("synapse-zeref-ibm-broker.service")
    assert "LoadCredential=ibm_quantum_token:/etc/synapse/credentials/ibm_quantum_token" in unit
    assert "ConditionPathExists=/etc/synapse/credentials/ibm_quantum_token" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "ReadWritePaths=/run/synapse/zeref" in unit
    assert "submit" not in unit.lower()

    launcher = (ROOT / "rootfs/usr/local/lib/synapse/zeref-ibm-broker").read_text(encoding="utf-8")
    assert "refresh_existing_job" in launcher
    assert "submit_real" not in launcher
    assert "IBM_QUANTUM_TOKEN" not in launcher
    assert "CREDENTIALS_DIRECTORY" in launcher


def test_broker_timer_is_not_enabled_by_default():
    hook = (ROOT / "build/hooks/010-synapse.hook.chroot").read_text(encoding="utf-8")
    assert "systemctl enable synapse-zeref.service" in hook
    assert "systemctl enable synapse-zeref-ibm-broker.timer" not in hook


def test_default_config_points_to_local_persistent_qc67_assets():
    config = (ROOT / "rootfs/etc/synapse/zeref.json").read_text(encoding="utf-8")
    assert "/var/lib/synapse/zeref/qc67/serving/cosmos_native_server.py" in config
    assert "/var/lib/synapse/zeref/qc67/qc67_cosmo.pt" in config
    assert "/run/synapse/zeref/ibm-receipt.json" in config
