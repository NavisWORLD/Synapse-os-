from __future__ import annotations


class NetworkAuthority:
    def __init__(self) -> None:
        self._status = {"online": False, "interface": None}
        self._control: set[str] = set()

    def update_status(self, *, online: bool, interface: str | None = None) -> None:
        self._status = {"online": bool(online), "interface": interface}

    def status(self) -> dict:
        return dict(self._status)

    def grant_control(self, operations: set[str]) -> None:
        allowed = {"status", "scan", "join", "disconnect"}
        unknown = set(operations) - allowed
        if unknown:
            raise ValueError(f"unsupported network operations: {sorted(unknown)}")
        self._control = set(operations)

    def can_control(self, operation: str | None = None) -> bool:
        if operation is None:
            return bool(self._control)
        return operation in self._control

    def request_control(self, operation: str) -> None:
        if not self.can_control(operation):
            raise PermissionError(f"network authority not granted: {operation}")
