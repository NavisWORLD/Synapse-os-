from __future__ import annotations
from dataclasses import dataclass
import ipaddress
from urllib.parse import urlparse


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
