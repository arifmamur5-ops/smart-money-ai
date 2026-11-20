"""Opt-in live read-only smoke check; invoke with ``python -m scripts.solana_rpc_smoke``."""

import os
import sys

from smart_money_ai.solana_observation import LiveFinalizedSlotAdapter, NetworkIdentity, ObservationError


def main() -> int:
    endpoint = os.environ.get("SOLANA_RPC_ENDPOINT")
    cluster = os.environ.get("SOLANA_CLUSTER")
    genesis_hash = os.environ.get("SOLANA_GENESIS_HASH")
    source_id = os.environ.get("SOLANA_SOURCE_ID", "manual-smoke")
    timeout = os.environ.get("SOLANA_RPC_TIMEOUT", "10")
    if not endpoint or not cluster or not genesis_hash:
        print("Set SOLANA_RPC_ENDPOINT, SOLANA_CLUSTER, and SOLANA_GENESIS_HASH to run the smoke check.")
        return 2

    try:
        adapter = LiveFinalizedSlotAdapter(
            endpoint=endpoint,
            network=NetworkIdentity(cluster=cluster, genesis_hash=genesis_hash),
            source_id=source_id,
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
