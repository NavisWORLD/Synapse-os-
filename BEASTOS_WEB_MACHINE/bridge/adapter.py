from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import subprocess
from typing import Any, Callable
from urllib.parse import urlparse


MAX_EXCHANGE_REQUEST = 16 * 1024
MAX_EXCHANGE_RESPONSE = 1024 * 1024


@dataclass(frozen=True)
class BeastRelease:
    tag: str
    commit: str
    asset: str
    sha256: str
    size: int
    prerelease: bool

    @classmethod
    def v060(cls) -> "BeastRelease":
        return cls(
            tag="v0.6.0",
            commit="331f03c5d6a4aab0b2e32314293e36c7a94be393",
            asset="beast-box-combined-0.6.0.zip",
            sha256="c2a5bf5e3cb972ec3e5f1aa45f06d7e77e9b6de115e049f06e830a1f4c312ad2",
            size=676405,
            prerelease=True,
        )


def _safe_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("invalid Beast endpoint")
    host = parsed.hostname or ""
    if host == "localhost":
        return endpoint.rstrip("/")
    try:
        if ipaddress.ip_address(host).is_loopback:
            return endpoint.rstrip("/")
    except ValueError:
        pass
    if parsed.scheme != "https":
        raise ValueError("non-loopback Beast endpoints require HTTPS")
    return endpoint.rstrip("/")


class BeastAdapter:
    """Provider-location descriptor used by the cockpit status surface."""

    PROVIDERS = {"BROWSER", "LOCAL_HOST", "LAN", "CLOUD"}

    def __init__(self, *, endpoint: str, provider: str) -> None:
        provider = provider.upper().strip()
        if provider not in self.PROVIDERS:
            raise ValueError(f"unsupported provider location: {provider}")
        self.endpoint = _safe_endpoint(endpoint)
        self.provider = provider
        self.release = BeastRelease.v060()

    def build_request(self, prompt: str, *, context: list[dict] | None = None) -> dict:
        return {
            "prompt": str(prompt),
            "context": list(context or []),
            "provider": self.provider,
            "allow_fallback": False,
            "beast_release": self.release.tag,
            "beast_commit": self.release.commit,
        }


class BeastExchangeAdapter:
    """Fixed subprocess adapter for Beast Box v0.6.0 ``runtime exchange``.

    The child process receives a bounded ``beastbox-request-v1`` document on
    stdin.  No caller-supplied executable arguments, shell string, filesystem
    path, URL, or secret value is accepted through the request body.
    """

    PROVIDERS = {"reference", "ollama", "compatible"}

    def __init__(
        self,
        *,
        data_dir: Path,
        executable: str = "beastbox",
        provider: str = "reference",
        model: str = "COSMOS reference",
        provider_url: str | None = None,
        allow_remote: bool = False,
        api_key_env: str | None = None,
        timeout: float = 120.0,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        provider = provider.strip().lower()
        if provider not in self.PROVIDERS:
            raise ValueError(f"unsupported Beast provider: {provider}")
        if not executable or any(ch in executable for ch in "\r\n\x00"):
            raise ValueError("invalid Beast executable")
        if not str(data_dir):
            raise ValueError("Beast data directory is required")
        if timeout <= 0 or timeout > 300:
            raise ValueError("Beast exchange timeout outside safe range")
        if api_key_env and (not api_key_env.replace("_", "").isalnum() or not api_key_env[0].isalpha()):
            raise ValueError("invalid API key environment-variable name")
        if provider_url:
            _safe_endpoint(provider_url)
            parsed = urlparse(provider_url)
            host = parsed.hostname or ""
            is_loopback = host == "localhost"
            if not is_loopback:
                try:
                    is_loopback = ipaddress.ip_address(host).is_loopback
                except ValueError:
                    is_loopback = False
            if not is_loopback and (provider != "compatible" or not allow_remote or parsed.scheme != "https"):
                raise ValueError("remote Beast provider requires compatible mode, HTTPS and explicit allow_remote")
        if provider == "ollama" and model == "COSMOS reference":
            raise ValueError("Ollama requires an explicit model")
        if provider == "compatible" and model == "COSMOS reference":
            raise ValueError("compatible provider requires an explicit model")
        self.data_dir = Path(data_dir)
        self.executable = executable
        self.provider = provider
        self.model = model
        self.provider_url = provider_url
        self.allow_remote = bool(allow_remote)
        self.api_key_env = api_key_env
        self.timeout = float(timeout)
        self.runner = runner

    def _argv(self) -> list[str]:
        argv = [
            self.executable,
            "runtime",
            "exchange",
            "--data-dir",
            str(self.data_dir),
            "--provider",
            self.provider,
            "--model",
            self.model,
        ]
        if self.provider_url:
            argv.extend(["--url", self.provider_url])
        if self.allow_remote:
            argv.append("--allow-remote")
        if self.api_key_env:
            argv.extend(["--api-key-env", self.api_key_env])
        return argv

    def _exchange(self, operation: str, *, text: str | None = None) -> dict[str, Any]:
        if operation not in {"chat", "inspect", "init"}:
            raise ValueError("unsupported Beast exchange operation")
        request: dict[str, Any] = {"schema": "beastbox-request-v1", "operation": operation}
        if operation == "chat":
            if text is None:
                raise ValueError("chat text is required")
            request["text"] = str(text)
        payload = json.dumps(request, separators=(",", ":"), ensure_ascii=False)
        if len(payload.encode("utf-8")) > MAX_EXCHANGE_REQUEST:
            raise ValueError("Beast exchange request exceeds 16384 bytes")
        try:
            result = self.runner(
                self._argv(),
                input=payload,
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Beast runtime unavailable: {exc}") from exc
        stdout = str(getattr(result, "stdout", "") or "")
        stderr = str(getattr(result, "stderr", "") or "").strip()
        if int(getattr(result, "returncode", 1)) != 0:
            message = stderr[:1000] or "Beast runtime exchange failed"
            raise RuntimeError(message)
        if len(stdout.encode("utf-8")) > MAX_EXCHANGE_RESPONSE:
            raise RuntimeError("Beast runtime response exceeds one MiB")
        try:
            response = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Beast runtime returned invalid JSON") from exc
        if (
            not isinstance(response, dict)
            or response.get("schema") != "beastbox-response-v1"
            or response.get("ok") is not True
            or "result" not in response
        ):
            raise RuntimeError("Beast runtime returned an invalid exchange response; no fallback")
        return response

    def chat(self, text: str) -> dict[str, Any]:
        return self._exchange("chat", text=text)

    def inspect(self) -> dict[str, Any]:
        return self._exchange("inspect")

    def init(self) -> dict[str, Any]:
        return self._exchange("init")
