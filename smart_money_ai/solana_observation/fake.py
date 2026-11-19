"""Deterministic fake implementation of the finalized slot observer."""

from collections.abc import Callable
from datetime import datetime, timezone

from smart_money_ai.solana_observation.interface import ObservationError
from smart_money_ai.solana_observation.models import (
    FinalizedSlotObservation,
    NetworkIdentity,
    ObservationSource,
)


class FakeSolanaObservationAdapter:
    """Return configured slot data using an injectable clock, without I/O."""

    def __init__(
        self,
        *,
        network: NetworkIdentity,
        slot: int,
        source: ObservationSource | None = None,
        clock: Callable[[], datetime] | None = None,
        fail: bool = False,
    ) -> None:
        if not isinstance(network, NetworkIdentity):
            raise TypeError("network must be a NetworkIdentity")
        if isinstance(slot, bool) or not isinstance(slot, int):
            raise TypeError("slot must be an integer")
        if slot < 0:
            raise ValueError("slot must be non-negative")
        if source is not None and not isinstance(source, ObservationSource):
            raise TypeError("source must be an ObservationSource")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        if not isinstance(fail, bool):
            raise TypeError("fail must be a boolean")

        self._network = network
        self._slot = slot
        self._source = source if source is not None else ObservationSource("fake")
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self._fail = fail

    def get_finalized_slot(self) -> FinalizedSlotObservation:
        """Return the configured finalized slot or raise a simulated failure."""
        if self._fail:
            raise ObservationError("simulated finalized slot observation failure")

        observed_at = self._clock()
        if not isinstance(observed_at, datetime):
            raise TypeError("clock must return a datetime")

        return FinalizedSlotObservation(
            network=self._network,
            slot=self._slot,
            commitment="finalized",
            source=self._source,
            observed_at=observed_at,
        )
