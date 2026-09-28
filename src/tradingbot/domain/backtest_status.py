"""
BacktestStatus enumeration model for tracking backtest lifecycle.
"""

from enum import Enum
from typing import Any, Dict


class BacktestStatus(str, Enum):
    """Enumeration of possible states in a backtest lifecycle.

    This model represents the lifecycle/state of a backtest, making it
    extensible for future phases.

    Attributes:
        PENDING: Backtest is initialized but not yet running
        RUNNING: Backtest is currently executing
        COMPLETED: Backtest has finished execution
        FAILED: Backtest failed during execution
        CANCELLED: Backtest was cancelled by user or system
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def from_string(cls, status_str: str) -> 'BacktestStatus':
        """Create a BacktestStatus from a string.

        Args:
            status_str: String representation of the status

        Returns:
            Corresponding BacktestStatus enum value

        Raises:
            ValueError: If the string doesn't match any status
        """
        try:
            return cls(status_str.lower())
        except ValueError as e:
            valid_values = [s.value for s in cls]
            raise ValueError(f"Invalid backtest status: '{status_str}'. "
                           f"Valid values are: {valid_values}") from e

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state (no further transitions possible)."""
        return self in (BacktestStatus.COMPLETED, BacktestStatus.FAILED, BacktestStatus.CANCELLED)

    @property
    def is_running(self) -> bool:
        """Check if this is the running state."""
        return self == BacktestStatus.RUNNING

    def to_dict(self) -> Dict[str, Any]:
        """Convert BacktestStatus to dictionary representation.

        Returns:
            Dictionary with status value and metadata
        """
        return {
            'value': self.value,
            'is_terminal': self.is_terminal,
            'is_running': self.is_running,
            'label': self.name
        }

    @classmethod
    def get_valid_transitions(cls, current: 'BacktestStatus') -> list:
        """Get valid state transitions from the current state.

        Args:
            current: Current backtest status

        Returns:
            List of valid next states
        """
        transitions = {
            BacktestStatus.PENDING: [BacktestStatus.RUNNING, BacktestStatus.CANCELLED],
            BacktestStatus.RUNNING: [BacktestStatus.COMPLETED, BacktestStatus.FAILED, BacktestStatus.CANCELLED],
            BacktestStatus.COMPLETED: [],
            BacktestStatus.FAILED: [BacktestStatus.CANCELLED],
            BacktestStatus.CANCELLED: [],
        }
        return transitions.get(current, [])
