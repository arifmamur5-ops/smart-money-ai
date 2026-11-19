"""Provider-neutral interface for finalized slot observation."""

from typing import Protocol

from smart_money_ai.solana_observation.models import FinalizedSlotObservation


class ObservationError(Exception):
    """Raised when a finalized slot observation cannot be obtained."""


class FinalizedSlotObserver(Protocol):
    """Synchronous contract for obtaining a finalized slot observation."""

    def get_finalized_slot(self) -> FinalizedSlotObservation:
        """Return the current finalized slot observation."""
