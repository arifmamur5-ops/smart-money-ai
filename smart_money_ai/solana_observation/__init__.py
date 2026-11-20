"""Provider-neutral models and fake adapter for Solana slot observation."""

from smart_money_ai.solana_observation.fake import FakeSolanaObservationAdapter
from smart_money_ai.solana_observation.interface import (
    FinalizedSlotObserver,
    ObservationError,
)
from smart_money_ai.solana_observation.live import LiveFinalizedSlotAdapter
from smart_money_ai.solana_observation.models import (
    FinalizedSlotObservation,
    NetworkIdentity,
    ObservationSource,
)

__all__ = [
    "FakeSolanaObservationAdapter",
    "FinalizedSlotObservation",
    "FinalizedSlotObserver",
    "LiveFinalizedSlotAdapter",
    "NetworkIdentity",
    "ObservationError",
    "ObservationSource",
]
