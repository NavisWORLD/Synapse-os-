from __future__ import annotations

import json
import os
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NetworkError(RuntimeError):
    pass


class _RedirectGuard(HTTPRedirectHandler):
    def __init__(self, checker):
        super().__init__(); self.checker = checker
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        absolute = urljoin(req.full_url, newurl)
        self.checker(absolute)
        return super().redirect_request(req, fp, code, msg, headers, absolute)


class NetworkClient:
    """Capability-gated HTTP/DNS/TCP/AI networking for Synapse Flow v2."""
    def __init__(self, capabilities: Any):
        self.cap = capabilities
        self.opener = build_opener(_RedirectGuard(self._url))

    def _require(self, host: str) -> None:
        if not bool(getattr(self.cap, "network", False)):
            raise NetworkError("network capability is disabled")
        allowed = {str(x).lower() for x in getattr(self.cap, "allowed_hosts", frozenset())}
        if not allowed:
            raise NetworkError("network enabled but no hosts were granted")
        if host.lower() not in allowed:
            raise NetworkError(f"host not allowed: {host}")

    def _url(self, url: str) -> tuple[str, str]:
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise NetworkError("only http/https URLs with a hostname are allowed")
        if parsed.username or parsed.password:
            raise NetworkError("credentials in URLs are not allowed")
        self._require(parsed.hostname)
        return parsed.scheme, parsed.hostname

    def _read(self, response: Any) -> bytes:
        limit = int(getattr(self.cap, "max_response_bytes", 2_000_000))
        data = response.read(limit + 1)
        if len(data) > limit: raise NetworkError("network response exceeded size limit")
        return data

    def _open(self, req: Request):
        try:
            return self.opener.open(req, timeout=float(getattr(self.cap, "timeout_seconds", 8.0)))
        except (HTTPError, URLError, OSError) as exc:
            raise NetworkError(f"network request failed: {exc}") from exc

    def get_text(self, url: str) -> str:
        self._url(url)
        req = Request(url, headers={"User-Agent":"SynapseFlow/2"})
        with self._open(req) as response:
            return self._read(response).decode("utf-8", errors="replace")

    def get_json(self, url: str) -> Any:
        try: return json.loads(self.get_text(url))
        except json.JSONDecodeError as exc: raise NetworkError("response was not valid JSON") from exc

    def post_json(self, url: str, payload: Any, headers: dict[str,str]|None=None) -> Any:
        self._url(url)
        body=json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode()
        if len(body)>1_000_000: raise NetworkError("request body exceeded size limit")
        hdr={"Content-Type":"application/json","Accept":"application/json","User-Agent":"SynapseFlow/2"}
        if headers: hdr.update(headers)
        req=Request(url,data=body,headers=hdr,method="POST")
        with self._open(req) as response: raw=self._read(response).decode("utf-8",errors="replace")
        try:return json.loads(raw)
        except json.JSONDecodeError as exc:raise NetworkError("response was not valid JSON") from exc

    def dns_lookup(self, host: str) -> list[str]:
        self._require(host)
        try: results=socket.getaddrinfo(host,None,type=socket.SOCK_STREAM)
        except OSError as exc: raise NetworkError(f"DNS lookup failed: {exc}") from exc
        return sorted({item[4][0] for item in results})

    def tcp_probe(self, host: str, port: int) -> bool:
        self._require(host)
        if not 1<=int(port)<=65535: raise NetworkError("port outside 1..65535")
        try:
            with socket.create_connection((host,int(port)),timeout=float(getattr(self.cap,"timeout_seconds",8.0))): return True
        except OSError:return False

    def ai_chat(self, endpoint: str, model: str, prompt: str, api_key_env: str) -> str:
        if not api_key_env or not api_key_env.replace("_","").isalnum(): raise NetworkError("invalid API-key environment variable name")
        token=os.environ.get(api_key_env)
        if not token: raise NetworkError(f"missing API key environment variable: {api_key_env}")
        result=self.post_json(endpoint.rstrip("/")+"/chat/completions",{"model":model,"messages":[{"role":"user","content":prompt}]},headers={"Authorization":f"Bearer {token}"})
        try:return str(result["choices"][0]["message"]["content"])
        except (KeyError,IndexError,TypeError) as exc:raise NetworkError("AI endpoint response did not match chat-completions schema") from exc
