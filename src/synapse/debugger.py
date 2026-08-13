from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from .flow import BytecodeModule, RuntimeCapabilities, VM


@dataclass
class Debugger:
    module: BytecodeModule
    breakpoints: set[int] = field(default_factory=set)
    events: list[dict[str, Any]] = field(default_factory=list)
    capabilities: RuntimeCapabilities = field(default_factory=RuntimeCapabilities)

    def _trace(self, event: dict[str, Any]) -> None:
        event = dict(event)
        event["breakpoint"] = event.get("line") in self.breakpoints
        self.events.append(event)

    def run(self) -> dict[str, Any]:
        result = VM(self.module, capabilities=self.capabilities, trace=self._trace).run()
        return {"result": result, "events": self.events}
