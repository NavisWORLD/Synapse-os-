#!/usr/bin/env python3
"""Loopback-only demo provider for the exact frozen Smol -> Zeref lineage.

This is an evidentiary adapter, not a production provider. It exposes the
minimal Ollama-compatible /api/generate endpoint expected by Beast Box v0.6.0
plus fixed-purpose localhost-only demo control/status endpoints. No arbitrary
model name, filesystem path, command, URL, or shell operation is accepted.
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from beastbox.persistent_substrate.models import TransformersNLLAdapter, ZerefNLLAdapter


SMOL_REPO = "HuggingFaceTB/SmolLM2-135M"
SMOL_REVISION = "4e53f736cbb20a9a0f56b4c4bf378d9f306ff915"
SMOL_PARAMETER_SHA256 = "109a74ae153ab55706aa31dcb1ae10f39fb281deea6728a3546b55d6dc0fcbb3"
ZEREF_CHECKPOINT_SHA256 = "454f3017618a81fb9a13393b215d448f365534baf5b607e19d1438955921e425"
ZEREF_ARCHITECTURE_SHA256 = "955805d45f7b407ef5cc9b6efe178d9a5f63df5b32eaf539d9aedcbb2967f1dc"
ZEREF_PARAMETER_SHA256 = "edf6501633ff26948a73815690e2f184c3e4025414c3ac2d64fbfec203307f7a"
MAX_BODY = 1 << 20


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class LineageState:
    def __init__(self, checkpoint: Path, architecture: Path) -> None:
        self._lock = threading.Lock()
        self.smol = TransformersNLLAdapter.from_pretrained(
            model_id=SMOL_REPO,
            revision=SMOL_REVISION,
            local_files_only=False,
        )
        if self.smol.identity["parameter_sha256"] != SMOL_PARAMETER_SHA256:
            raise RuntimeError("Smol loaded-parameter SHA mismatch")
        self.zeref = ZerefNLLAdapter.from_checkpoint(
            checkpoint,
            architecture,
            expected_checkpoint_sha256=ZEREF_CHECKPOINT_SHA256,
            expected_architecture_sha256=ZEREF_ARCHITECTURE_SHA256,
            model_id="zeref-pinned-active-checkpoint",
        )
        if self.zeref.identity["parameter_sha256"] != ZEREF_PARAMETER_SHA256:
            raise RuntimeError("Zeref loaded-parameter SHA mismatch")
        self.active = "smol"
        self.generation_count = {"smol": 0, "zeref": 0}
        self.last_fit: dict[str, Any] = {}

    def identities(self) -> dict[str, Any]:
        return {
            "smol": dict(self.smol.identity),
            "zeref": dict(self.zeref.identity),
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": "beastos-smol-zeref-lineage-status-v1",
                "active": self.active,
                "identities": self.identities(),
                "generation_count": dict(self.generation_count),
                "last_fit": dict(self.last_fit),
                "training_performed": False,
                "authority_owned_by_provider": False,
            }

    def switch(self, brain: str) -> dict[str, Any]:
        requested = str(brain).strip().lower()
        if requested not in {"smol", "zeref"}:
            raise ValueError("brain must be exactly smol or zeref")
        with self._lock:
            previous = self.active
            self.active = requested
            return {
                "schema": "beastos-smol-zeref-swap-v1",
                "previous": previous,
                "active": self.active,
                "authority_transferred": False,
            }

    def _fit_smol(self, prompt: str, budget: int) -> str:
        tokenizer = self.smol.tokenizer
        ids = [int(value) for value in tokenizer.encode(prompt, add_special_tokens=False)]
        context_limit = int(getattr(self.smol.model.config, "max_position_embeddings", 2048) or 2048)
        keep = max(1, context_limit - budget)
        dropped = max(0, len(ids) - keep)
        if dropped:
            ids = ids[-keep:]
            fitted = str(tokenizer.decode(ids, skip_special_tokens=False))
        else:
            fitted = prompt
        self.last_fit = {
            "brain": "smol",
            "source_units": len(ids) + dropped,
            "dropped_units": dropped,
            "budget": budget,
        }
        return fitted

    def _fit_zeref(self, prompt: str, budget: int) -> str:
        stoi = self.zeref.stoi
        replacement = " " if " " in stoi else next(iter(stoi))
        filtered_chars: list[str] = []
        replaced = 0
        for character in prompt:
            if character in stoi:
                filtered_chars.append(character)
            else:
                filtered_chars.append(replacement)
                replaced += 1
        block_size = int(self.zeref.block_size or 1)
        keep = max(1, block_size - budget)
        source_units = len(filtered_chars)
        dropped = max(0, source_units - keep)
        if dropped:
            filtered_chars = filtered_chars[-keep:]
        self.last_fit = {
            "brain": "zeref",
            "source_units": source_units,
            "dropped_units": dropped,
            "replaced_characters": replaced,
            "budget": budget,
            "block_size": block_size,
        }
        return "".join(filtered_chars)

    def generate(self, prompt: str) -> tuple[str, dict[str, Any]]:
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("prompt must be a non-empty string")
        with self._lock:
            brain = self.active
            if brain == "smol":
                budget = 72
                fitted = self._fit_smol(prompt, budget)
                result = self.smol.generate(fitted, max_new_tokens=budget)
            else:
                # The frozen Zeref checkpoint is character-level and has a bounded block.
                budget = min(180, max(24, int(self.zeref.block_size or 256) // 3))
                fitted = self._fit_zeref(prompt, budget)
                result = self.zeref.generate(fitted, max_new_tokens=budget)
            self.generation_count[brain] += 1
            metadata = {
                "brain": brain,
                "model_id": result["model_id"],
                "generated_units": result["generated_units"],
                "unit_kind": result["unit_kind"],
                "generated_ids_sha256": result["generated_ids_sha256"],
                "prompt_ids_sha256": result["prompt_ids_sha256"],
                "parameter_sha256": result["parameter_sha256"],
                "fit": dict(self.last_fit),
            }
            return str(result["text"]), metadata

    def close_receipt(self) -> dict[str, Any]:
        with self._lock:
            smol = self.smol.close()
            zeref = self.zeref.close()
            if smol.get("parameter_drift") is not False or zeref.get("parameter_drift") is not False:
                raise RuntimeError("frozen model parameter_drift detected")
            return {
                "schema": "beastos-smol-zeref-close-v1",
                "smol": smol,
                "zeref": zeref,
                "generation_count": dict(self.generation_count),
            }


class Handler(BaseHTTPRequestHandler):
    server_version = "BeastOSLineageProvider/1"

    @property
    def state(self) -> LineageState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        # Method/path/status only; request bodies/prompts are never logged here.
        super().log_message(fmt, *args)

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        raw = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > MAX_BODY:
            raise ValueError("invalid request size")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/demo/status":
            self._send(200, self.state.status())
            return
        if self.path == "/v1/health":
            self._send(200, {"ok": True, "active": self.state.status()["active"]})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self._read_json()
            if self.path == "/demo/brain":
                if set(payload) != {"brain"}:
                    raise ValueError("brain control accepts only the brain field")
                self._send(200, self.state.switch(str(payload["brain"])))
                return
            if self.path == "/demo/close":
                if payload:
                    raise ValueError("close accepts an empty object only")
                self._send(200, self.state.close_receipt())
                return
            if self.path == "/api/generate":
                if not set(payload).issubset({"model", "prompt", "stream", "options"}):
                    raise ValueError("unsupported generate request field")
                prompt = payload.get("prompt")
                if not isinstance(prompt, str):
                    raise ValueError("prompt string required")
                text, metadata = self.state.generate(prompt)
                self._send(
                    200,
                    {
                        "model": metadata["model_id"],
                        "response": text,
                        "done": True,
                        "done_reason": "stop",
                        "beastos_lineage": metadata,
                    },
                )
                return
            self._send(404, {"error": "not found"})
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # fail closed, no model fallback
            self._send(503, {"error": f"lineage provider unavailable: {type(exc).__name__}"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Exact frozen Smol -> Zeref localhost demo provider")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11436)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.listen not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("lineage provider is loopback-only")
    state = LineageState(Path(args.checkpoint), Path(args.architecture))
    server = ThreadingHTTPServer((args.listen, int(args.port)), Handler)
    server.state = state  # type: ignore[attr-defined]
    print(json.dumps({"event": "LINEAGE_PROVIDER_READY", **state.status()}, sort_keys=True), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
