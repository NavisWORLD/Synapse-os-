from __future__ import annotations
from dataclasses import dataclass
from time import time


@dataclass(frozen=True)
class AuthorityEvent:
    event: str
    brain: str | None
    capability: str | None
    at: float


class AuthorityLedger:
    """Brain-scoped authority. Clock-in always revokes the previous brain's grants."""

    def __init__(self) -> None:
        self.active_brain: str | None = None
        self._grants: set[str] = set()
        self.events: list[AuthorityEvent] = []

    def clock_in(self, brain: str) -> set[str]:
        brain = brain.strip()
        if not brain:
            raise ValueError("brain identifier is required")
        revoked = set(self._grants)
        self._grants.clear()
        self.active_brain = brain
        self.events.append(AuthorityEvent("clock_in", brain, None, time()))
        for capability in sorted(revoked):
            self.events.append(AuthorityEvent("model_swap_revoke", brain, capability, time()))
        return revoked

    def grant(self, capability: str) -> None:
        if self.active_brain is None:
            raise PermissionError("no active brain")
        capability = capability.strip()
        if not capability:
            raise ValueError("capability is required")
        self._grants.add(capability)
        self.events.append(AuthorityEvent("grant", self.active_brain, capability, time()))

    def revoke(self, capability: str) -> bool:
        existed = capability in self._grants
        self._grants.discard(capability)
        if existed:
            self.events.append(AuthorityEvent("revoke", self.active_brain, capability, time()))
        return existed

    def allowed(self, capability: str) -> bool:
        return self.active_brain is not None and capability in self._grants

    def grants(self) -> set[str]:
        return set(self._grants)

    def master_privacy_stop(self) -> set[str]:
        revoked = set(self._grants)
        self._grants.clear()
        for capability in sorted(revoked):
            self.events.append(AuthorityEvent("privacy_revoke", self.active_brain, capability, time()))
        return revoked
