from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyState:
    safe_mode: bool
    kill_switch: bool
    reasons: tuple[str, ...]

    @property
    def can_open_new_positions(self) -> bool:
        return not self.safe_mode and not self.kill_switch


class SafetyController:
    """Central safe-mode / kill-switch controller.

    Phase 1 is in-memory and conservative. Later phases will persist incidents,
    connect alerts, and enforce this state inside live execution.
    """

    def __init__(self) -> None:
        self._safe_mode = False
        self._kill_switch = False
        self._reasons: list[str] = []

    def enable_safe_mode(self, reason: str) -> None:
        self._safe_mode = True
        self._reasons.append(reason)

    def enable_kill_switch(self, reason: str) -> None:
        self._kill_switch = True
        self._safe_mode = True
        self._reasons.append(reason)

    def clear_safe_mode(self) -> None:
        if not self._kill_switch:
            self._safe_mode = False
            self._reasons.clear()

    def state(self) -> SafetyState:
        return SafetyState(
            safe_mode=self._safe_mode,
            kill_switch=self._kill_switch,
            reasons=tuple(self._reasons),
        )
