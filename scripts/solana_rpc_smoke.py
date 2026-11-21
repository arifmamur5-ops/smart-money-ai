"""Opt-in live read-only smoke check; invoke with ``python -m scripts.solana_rpc_smoke``."""

import sys

from smart_money_ai.config import Settings, load_settings
from smart_money_ai.solana_observation import LiveFinalizedSlotAdapter, NetworkIdentity, ObservationError


def main(settings: Settings | None = None) -> int:
    runtime_settings = settings if settings is not None else load_settings()
    endpoint = runtime_settings.solana_rpc_endpoint
    cluster = runtime_settings.solana_cluster
    genesis_hash = runtime_settings.solana_genesis_hash
    timeout = runtime_settings.solana_rpc_timeout_seconds
    if (
        endpoint is None or not endpoint.strip()
        or cluster is None or not cluster.strip()
        or genesis_hash is None or not genesis_hash.strip()
        or timeout is None or not timeout.strip()
    ):
        print(
            "Set SOLANA_RPC_ENDPOINT, SOLANA_CLUSTER, SOLANA_GENESIS_HASH, and "
            "SOLANA_RPC_TIMEOUT_SECONDS to run the smoke check."
        )
        return 2

    try:
        adapter = LiveFinalizedSlotAdapter(
            endpoint=endpoint,
            network=NetworkIdentity(cluster=cluster, genesis_hash=genesis_hash),
            source_id=runtime_settings.solana_rpc_source_id,
            timeout=float(timeout),
        )
        observation = adapter.get_finalized_slot()
    except (ObservationError, TypeError, ValueError):
        print("Smoke check failed; details were suppressed to protect endpoint credentials and response data.")
        return 1

    print(
        "Smoke check succeeded: "
        f"cluster={observation.network.cluster}, "
        f"source_id={observation.source.source_id}, "
        f"commitment={observation.commitment}, "
        f"slot={observation.slot}, "
        f"observed_at={observation.observed_at.isoformat()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
