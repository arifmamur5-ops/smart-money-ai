"""Immutable domain models for finalized Solana slot observations."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal


@dataclass(frozen=True, slots=True)
class NetworkIdentity:
    """Identify a Solana network by its cluster label and genesis hash."""

    cluster: str
    genesis_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.cluster, str):
            raise TypeError("cluster must be a string")
        if not self.cluster.strip():
            raise ValueError("cluster must not be empty")
        if not isinstance(self.genesis_hash, str):
            raise TypeError("genesis_hash must be a string")
        if not self.genesis_hash.strip():
            raise ValueError("genesis_hash must not be empty")


@dataclass(frozen=True, slots=True)
class ObservationSource:
    """Identify the source of an observation without naming a provider."""

    source_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str):
            raise TypeError("source_id must be a string")
        if not self.source_id.strip():
            raise ValueError("source_id must not be empty")


@dataclass(frozen=True, slots=True)
class FinalizedSlotObservation:
    """Represent a slot observed at finalized commitment."""

    network: NetworkIdentity
    slot: int
    commitment: Literal["finalized"]
    source: ObservationSource
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.network, NetworkIdentity):
            raise TypeError("network must be a NetworkIdentity")
        if isinstance(self.slot, bool) or not isinstance(self.slot, int):
            raise TypeError("slot must be an integer")
        if self.slot < 0:
            raise ValueError("slot must be non-negative")
        if self.commitment != "finalized":
            raise ValueError('commitment must be "finalized"')
        if not isinstance(self.source, ObservationSource):
            raise TypeError("source must be an ObservationSource")
        if not isinstance(self.observed_at, datetime):
            raise TypeError("observed_at must be a datetime")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")

        object.__setattr__(self, "observed_at", self.observed_at.astimezone(timezone.utc))
