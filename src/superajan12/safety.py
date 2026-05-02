from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class SafetyState:
    safe_mode: bool
    kill_switch: bool
    stale_data_lock: bool
    disconnect_lock: bool
    reasons: tuple[str, ...]

    @property
    def can_open_new_positions(self) -> bool:
        return not (self.safe_mode or self.kill_switch or self.stale_data_lock or self.disconnect_lock)


class SafetyController:
    """Central safe-mode / kill-switch controller.

    Phase 1 is in-memory and conservative. Later phases will persist incidents,
    connect alerts, and enforce this state inside live execution.
    """

    def __init__(self) -> None:
        self._safe_mode = False
        self._kill_switch = False
        self._stale_data_lock = False
        self._disconnect_lock = False
        self._safe_mode_reason: str | None = None
        self._kill_switch_reason: str | None = None
        self._stale_data_reason: str | None = None
        self._disconnect_reason: str | None = None

    def enable_safe_mode(self, reason: str) -> None:
        self._safe_mode = True
        self._safe_mode_reason = reason

    def enable_kill_switch(self, reason: str) -> None:
        self._kill_switch = True
        self._kill_switch_reason = reason
        if not self._safe_mode:
            self._safe_mode = True
            self._safe_mode_reason = "kill-switch enabled"

    def enable_stale_data_lock(self, reason: str) -> None:
        self._stale_data_lock = True
        self._stale_data_reason = reason

    def clear_stale_data_lock(self) -> None:
        self._stale_data_lock = False
        self._stale_data_reason = None

    def enable_disconnect_lock(self, reason: str) -> None:
        self._disconnect_lock = True
        self._disconnect_reason = reason
        if not self._safe_mode:
            self._safe_mode = True
            self._safe_mode_reason = "disconnect lock enabled"

    def clear_disconnect_lock(self) -> None:
        self._disconnect_lock = False
        self._disconnect_reason = None
        if self._safe_mode and self._safe_mode_reason == "disconnect lock enabled":
            self._safe_mode = False
            self._safe_mode_reason = None

    def clear_safe_mode(self) -> None:
        self._safe_mode = False
        self._kill_switch = False
        self._stale_data_lock = False
        self._disconnect_lock = False
        self._safe_mode_reason = None
        self._kill_switch_reason = None
        self._stale_data_reason = None
        self._disconnect_reason = None

    def disable_kill_switch(self) -> None:
        self._kill_switch = False
        self._kill_switch_reason = None
        if self._safe_mode and self._safe_mode_reason == "kill-switch enabled":
            self._safe_mode = False
            self._safe_mode_reason = None

    def state(self) -> SafetyState:
        reasons = tuple(
            reason
            for reason in (
                self._safe_mode_reason,
                self._kill_switch_reason,
                self._stale_data_reason,
                self._disconnect_reason,
            )
            if reason
        )
        return SafetyState(
            safe_mode=self._safe_mode,
            kill_switch=self._kill_switch,
            stale_data_lock=self._stale_data_lock,
            disconnect_lock=self._disconnect_lock,
            reasons=reasons,
        )


@lru_cache(maxsize=1)
def get_safety_controller() -> SafetyController:
    return SafetyController()
