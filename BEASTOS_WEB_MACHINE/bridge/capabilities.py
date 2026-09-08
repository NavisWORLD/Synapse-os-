from __future__ import annotations
from enum import Enum


class CapabilityState(str, Enum):
    SUPPORTED = "SUPPORTED"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"
    UNAVAILABLE = "UNAVAILABLE"


class CapabilityRegistry:
    def __init__(self) -> None:
        self._states: dict[str, CapabilityState] = {}

    def observe(self, name: str, *, supported: bool, permission_required: bool = False) -> CapabilityState:
        if not supported:
            state = CapabilityState.UNAVAILABLE
        elif permission_required:
            state = CapabilityState.PERMISSION_REQUIRED
        else:
            state = CapabilityState.SUPPORTED
        self._states[name] = state
        return state

    def state(self, name: str) -> CapabilityState:
        return self._states.get(name, CapabilityState.UNAVAILABLE)

    def authorize(self, name: str) -> None:
        if self.state(name) == CapabilityState.UNAVAILABLE:
            raise ValueError(f"capability unavailable: {name}")
        self._states[name] = CapabilityState.AUTHORIZED

    def deny(self, name: str) -> None:
        if self.state(name) != CapabilityState.UNAVAILABLE:
            self._states[name] = CapabilityState.DENIED

    def snapshot(self) -> dict[str, str]:
        return {name: state.value for name, state in sorted(self._states.items())}
