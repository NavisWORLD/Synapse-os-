from __future__ import annotations

import json
import time
from typing import Any

from .genesis import GenesisError, GenesisManager, EXPECTED_LICENSE, EXPECTED_ZENODO_DOI, PLAN_SCHEMA
from .genesis_writer import run_install


GENESIS_V1_PHYSICAL_PROFILE = "asus-cx1700cka-gallop"


class InstallerGenesisManager(GenesisManager):
    """GENESIS manager variant used only by the kernel-gated root installer service."""

    def preflight(self) -> dict[str, Any]:
        result = super().preflight()
        if not self.installer_mode or self.simulation:
            return result

        hardware = result.get("hardware") or {}
        if hardware.get("profile_id") != GENESIS_V1_PHYSICAL_PROFILE:
            raise GenesisError(
                "HARDWARE_UNSUPPORTED",
                "GENESIS v1 destructive installation is locked to the ASUS CX1700CKA / GALLOP profile",
            )

        power = result.get("power") or {}
        ac_online = power.get("ac_online")
        battery = power.get("battery_percent")
        known_safe_power = ac_online is True or (battery is not None and float(battery) >= 50.0)
        if not known_safe_power:
            raise GenesisError(
                "POWER_INSUFFICIENT",
                "GENESIS destructive installation requires detected external power or at least 50% battery",
            )

        boot = result.get("boot") or {}
        if boot.get("mode") != "uefi":
            raise GenesisError(
                "INSTALLER_DISABLED",
                "GENESIS v1 destructive installation requires a UEFI boot environment",
            )
        if not boot.get("genesis_kernel_marker"):
            raise GenesisError(
                "INSTALLER_DISABLED",
                "GENESIS v1 destructive installation requires kernel marker synapse.genesis=1",
            )
        return result

    def _worker(self, preflight: dict[str, Any]) -> None:
        try:
            self._phase("staging", 20, "writing immutable GENESIS install plan")
            self.staging_dir.mkdir(parents=True, exist_ok=True)
            plan_path = self.staging_dir / "install-plan.json"
            receipt_path = self.staging_dir / "receipt.json"
            plan = {
                "schema": PLAN_SCHEMA,
                "created_at": time.time(),
                "device_fingerprint": preflight["device_fingerprint"],
                "target": preflight["target"],
                "image_path": str(self.image_path),
                "manifest_path": str(self.manifest_path),
                "image_sha256": preflight["image"]["image_sha256"],
                "architecture": preflight["hardware"].get("arch"),
                "license": EXPECTED_LICENSE,
                "zenodo_doi": EXPECTED_ZENODO_DOI,
            }
            plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            if self.simulation:
                self._phase("installing", 55, "simulation: destructive writer not invoked")
                self._phase("verifying", 85, "simulation: install plan and provenance verified")
                self._phase("complete", 100, "GENESIS simulation complete")
                with self._lock:
                    if self._receipt is not None:
                        self._receipt["final_state"] = "complete"
                        self._receipt["finished_at"] = time.time()
                        self._persist_receipt_locked()
                return

            if not self.installer_mode:
                raise GenesisError("INSTALLER_DISABLED", "destructive installer mode is disabled")

            self._phase("installing", 45, "GENESIS writer is installing Synapse OS")
            result = run_install(plan_path, receipt_path, execute=True)
            if result.get("final_state") != "complete":
                raise GenesisError("WRITE_FAILED", "GENESIS writer did not report a complete installation")
            with self._lock:
                self._receipt = result
                self._state = {
                    "phase": "complete",
                    "progress": 100,
                    "message": "Synapse OS installation verified",
                    "error": None,
                }
                self._persist_receipt_locked()
        except GenesisError as exc:
            with self._lock:
                self._state = {
                    "phase": "failed",
                    "progress": self._state.get("progress", 0),
                    "message": exc.message,
                    "error": {"code": exc.code, "message": exc.message},
                }
                if self._receipt is not None:
                    self._receipt.setdefault("phases", []).append(
                        {"phase": "failed", "at": time.time(), "message": exc.message}
                    )
                    self._receipt["final_state"] = "failed"
                    self._receipt["error"] = {"code": exc.code, "message": exc.message}
                    self._receipt["finished_at"] = time.time()
                    self._persist_receipt_locked()
        except Exception as exc:
            wrapped = GenesisError("WRITE_FAILED", f"GENESIS writer failed: {exc}")
            with self._lock:
                self._state = {
                    "phase": "failed",
                    "progress": self._state.get("progress", 0),
                    "message": wrapped.message,
                    "error": {"code": wrapped.code, "message": wrapped.message},
                }
                if self._receipt is not None:
                    self._receipt.setdefault("phases", []).append(
                        {"phase": "failed", "at": time.time(), "message": wrapped.message}
                    )
                    self._receipt["final_state"] = "failed"
                    self._receipt["error"] = {"code": wrapped.code, "message": wrapped.message}
                    self._receipt["finished_at"] = time.time()
                    self._persist_receipt_locked()
