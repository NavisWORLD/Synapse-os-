from __future__ import annotations
from enum import Enum
import secrets


class FileScope(str, Enum):
    TEMPORARY_ATTACHMENT = "TEMPORARY_ATTACHMENT"
    CONVERSATION_CONTEXT = "CONVERSATION_CONTEXT"
    WORKSPACE_KNOWLEDGE = "WORKSPACE_KNOWLEDGE"
    PERSISTENT_BEAST_MEMORY = "PERSISTENT_BEAST_MEMORY"
    VM_EPHEMERAL_STORAGE = "VM_EPHEMERAL_STORAGE"


class FileScopePolicy:
    def __init__(self) -> None:
        self._tokens: dict[str, tuple[FileScope, FileScope]] = {}

    def initial_upload_scope(self) -> FileScope:
        return FileScope.TEMPORARY_ATTACHMENT

    def authorize_transfer(self, source: FileScope, destination: FileScope) -> str:
        if source == destination:
            raise ValueError("transfer must cross a scope boundary")
        token = secrets.token_urlsafe(24)
        self._tokens[token] = (source, destination)
        return token

    def can_transfer(self, source: FileScope, destination: FileScope, *, token: str | None = None) -> bool:
        if source == destination:
            return True
        if not token:
            return False
        expected = self._tokens.pop(token, None)
        return expected == (source, destination)
