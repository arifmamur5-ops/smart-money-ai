"""FastAPI application factory and application wiring."""

from fastapi import FastAPI, HTTPException

from smart_money_ai.config import Settings, load_settings
from smart_money_ai.solana_observation import (
    FinalizedSlotObserver,
    LiveFinalizedSlotAdapter,
    NetworkIdentity,
    ObservationError,
)


_RPC_NOT_CONFIGURED = "not_configured"
_RPC_CONFIGURATION_INVALID = "invalid"
_RPC_READY = "ready"


def _configured_observer(settings: Settings) -> tuple[FinalizedSlotObserver | None, str]:
    """Build the configured observer without making an RPC request."""
    values = (
        settings.solana_rpc_endpoint,
        settings.solana_cluster,
        settings.solana_genesis_hash,
        settings.solana_rpc_timeout_seconds,
    )
    if all(value is None for value in values):
        return None, _RPC_NOT_CONFIGURED
    if any(not isinstance(value, str) or not value.strip() for value in values):
        return None, _RPC_CONFIGURATION_INVALID

    endpoint, cluster, genesis_hash, timeout_value = values
    try:
        observer = LiveFinalizedSlotAdapter(
            endpoint=endpoint,
            network=NetworkIdentity(cluster=cluster, genesis_hash=genesis_hash),
            source_id=settings.solana_rpc_source_id,
            timeout=float(timeout_value),
        )
    except (TypeError, ValueError):
        return None, _RPC_CONFIGURATION_INVALID
    return observer, _RPC_READY


def create_app(
    settings: Settings | None = None,
    *,
    finalized_slot_observer: FinalizedSlotObserver | None = None,
) -> FastAPI:
    """Create the application without requiring optional Solana RPC settings."""
    runtime_settings = settings if settings is not None else load_settings()
    application = FastAPI(title=runtime_settings.app_name)
    application.state.settings = runtime_settings
    if finalized_slot_observer is None:
        observer, observer_status = _configured_observer(runtime_settings)
    else:
        observer, observer_status = finalized_slot_observer, _RPC_READY
    application.state.finalized_slot_observer = observer
    application.state.solana_rpc_configuration_status = observer_status

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Report that the application process can serve requests."""
        return {"status": "ok"}

    @application.get("/solana/observations/finalized-slot", tags=["solana"])
    def finalized_slot_observation() -> dict[str, object]:
        """Request and return one finalized slot observation."""
        current_observer = application.state.finalized_slot_observer
        if current_observer is None:
            if application.state.solana_rpc_configuration_status == _RPC_CONFIGURATION_INVALID:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "solana_rpc_configuration_invalid",
                        "message": "Solana RPC configuration is invalid",
                    },
                )
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "solana_rpc_not_configured",
                    "message": "Solana RPC observation is not configured",
                },
            )

        try:
            observation = current_observer.get_finalized_slot()
            return {
                "network": {
                    "cluster": observation.network.cluster,
                    "genesis_hash": observation.network.genesis_hash,
                },
                "slot": observation.slot,
                "commitment": observation.commitment,
                "source": {"source_id": observation.source.source_id},
                "observed_at": observation.observed_at.isoformat(),
            }
        except ObservationError:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "solana_observation_failed",
                    "message": "Finalized slot observation failed",
                },
            ) from None
        except Exception:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "internal_error",
                    "message": "An internal error occurred",
                },
            ) from None

    return application
