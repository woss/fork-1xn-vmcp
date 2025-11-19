"""In-memory tail for sandbox violations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from sandbox_runtime.sandbox.utils import encode_sandboxed_command


@dataclass
class SandboxViolationEvent:
    """Represents a sandbox violation event."""

    line: str
    command: Optional[str] = None
    encoded_command: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        """Set default timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()


class SandboxViolationStore:
    """In-memory store for sandbox violations."""

    def __init__(self, max_size: int = 100):
        """Initialize the violation store.

        Args:
            max_size: Maximum number of violations to store
        """
        self._violations: list[SandboxViolationEvent] = []
        self._total_count = 0
        self._max_size = max_size
        self._listeners: set[Callable[[list[SandboxViolationEvent]], None]] = set()

    def add_violation(self, violation: SandboxViolationEvent) -> None:
        """Add a violation to the store."""
        self._violations.append(violation)
        self._total_count += 1
        if len(self._violations) > self._max_size:
            self._violations = self._violations[-self._max_size :]
        self._notify_listeners()

    def get_violations(self, limit: Optional[int] = None) -> list[SandboxViolationEvent]:
        """Get violations, optionally limited to the most recent N."""
        if limit is None:
            return self._violations.copy()
        return self._violations[-limit:]

    def get_count(self) -> int:
        """Get the current number of violations in the store."""
        return len(self._violations)

    def get_total_count(self) -> int:
        """Get the total number of violations ever added."""
        return self._total_count

    def get_violations_for_command(self, command: str) -> list[SandboxViolationEvent]:
        """Get violations for a specific command."""
        command_base64 = encode_sandboxed_command(command)
        return [
            v
            for v in self._violations
            if v.encoded_command == command_base64
        ]

    def clear(self) -> None:
        """Clear all violations from the store."""
        self._violations = []
        # Don't reset total_count when clearing
        self._notify_listeners()

    def subscribe(
        self, listener: Callable[[list[SandboxViolationEvent]], None]
    ) -> Callable[[], None]:
        """Subscribe to violation updates.

        Args:
            listener: Callback function that receives violations

        Returns:
            Unsubscribe function
        """
        self._listeners.add(listener)
        listener(self.get_violations())

        def unsubscribe():
            self._listeners.discard(listener)

        return unsubscribe

    def _notify_listeners(self) -> None:
        """Notify all listeners of current violations."""
        violations = self.get_violations()
        for listener in self._listeners:
            listener(violations)

