"""Read-only HTTPS JSON-RPC adapter for finalized Solana slot observations."""

from collections.abc import Callable
from datetime import datetime, timezone
from http.client import HTTPException
import json
import math
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from smart_money_ai.solana_observation.interface import ObservationError
from smart_money_ai.solana_observation.models import (
    FinalizedSlotObservation,
    MAX_U64_SLOT,
    NetworkIdentity,
    ObservationSource,
)

_MAX_RPC_RESPONSE_BYTES = 64 * 1024
_Transport = Callable[[Request, float], Any]


class _RedirectRejected(Exception):
    """Internal marker raised when urllib encounters an HTTP redirect."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        if fp is not None:
            try:
                fp.close()
            except OSError:
                # Preserve redirect rejection as the public outcome.
                pass
        raise _RedirectRejected


def _stdlib_post(request: Request, timeout: float) -> Any:
    """Open one request with verified TLS and redirects disabled."""
    return build_opener(_NoRedirectHandler()).open(request, timeout=timeout)


class LiveFinalizedSlotAdapter:
    """Fetch one finalized slot after verifying the endpoint's genesis hash.

    ``timeout`` applies separately to each of the two RPC requests.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        network: NetworkIdentity,
        source_id: str,
        timeout: float,
        clock: Callable[[], datetime] | None = None,
        _transport: _Transport | None = None,
    ) -> None:
        self._validate_endpoint(endpoint)
        if not isinstance(network, NetworkIdentity):
            raise TypeError("network must be a NetworkIdentity")
        if not isinstance(source_id, str):
            raise TypeError("source_id must be a string")
        if not source_id.strip():
            raise ValueError("source_id must not be empty")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise TypeError("timeout must be a finite positive number")
        try:
            normalized_timeout = float(timeout)
        except OverflowError:
            raise ValueError("timeout must be a finite positive number") from None
        if not math.isfinite(normalized_timeout) or normalized_timeout <= 0:
            raise ValueError("timeout must be a finite positive number")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        if _transport is not None and not callable(_transport):
            raise TypeError("transport must be callable")

        self._endpoint = endpoint
        self._network = network
        self._source = ObservationSource(source_id)
        self._timeout = normalized_timeout
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self._transport = _transport if _transport is not None else _stdlib_post

    @staticmethod
    def _validate_endpoint(endpoint: str) -> None:
        if not isinstance(endpoint, str):
            raise TypeError("endpoint must be a string")
        try:
            parsed = urlsplit(endpoint)
            valid = (
                parsed.scheme.lower() == "https"
                and parsed.hostname is not None
                and bool(parsed.hostname)
                and parsed.port != 0
                and not parsed.fragment
                and not any(char.isspace() or ord(char) < 32 for char in endpoint)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("endpoint must be a valid HTTPS URL with a host")

    def get_finalized_slot(self) -> FinalizedSlotObservation:
        """Verify network identity, then return its finalized slot."""
        genesis_hash = self._rpc_call("getGenesisHash", [], 1)
        if not isinstance(genesis_hash, str) or not genesis_hash.strip():
            raise ObservationError("getGenesisHash returned an invalid result")
        if genesis_hash != self._network.genesis_hash:
            raise ObservationError("getGenesisHash did not match the configured network")

        slot = self._rpc_call("getSlot", [{"commitment": "finalized"}], 2)
        if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot <= MAX_U64_SLOT:
            raise ObservationError("getSlot returned an invalid slot value")

        try:
            observed_at = self._clock()
        except Exception:
            raise ObservationError("observation clock failed") from None
        if not isinstance(observed_at, datetime):
            raise ObservationError("observation clock must return a datetime")
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ObservationError("observation clock must return a timezone-aware datetime")

        return FinalizedSlotObservation(
            network=self._network,
            slot=slot,
            commitment="finalized",
            source=self._source,
            observed_at=observed_at,
        )

    def _rpc_call(self, method: str, params: list[object], request_id: int) -> object:
        body = json.dumps(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            self._endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            response = self._transport(request, self._timeout)
            with response:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                if not isinstance(status, int) or not 200 <= status < 300:
                    raise ObservationError(f"{method} returned an HTTP error")
                raw_body = response.read(_MAX_RPC_RESPONSE_BYTES + 1)
                if len(raw_body) > _MAX_RPC_RESPONSE_BYTES:
                    raise ObservationError(f"{method} response exceeded the maximum permitted size")
        except _RedirectRejected:
            raise ObservationError(f"{method} redirect was rejected") from None
        except HTTPError as exc:
            try:
                exc.close()
            except OSError:
                # Preserve the sanitized mapping for the original HTTP failure.
                pass
            if 300 <= exc.code < 400:
                raise ObservationError(f"{method} redirect was rejected") from None
            raise ObservationError(f"{method} returned an HTTP error") from None
        except (TimeoutError, URLError, OSError, HTTPException):
            raise ObservationError(f"{method} transport failed or timed out") from None

        try:
            payload = json.loads(
                raw_body.decode("utf-8"),
                parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise ObservationError(f"{method} returned invalid JSON") from None

        if not isinstance(payload, dict):
            raise ObservationError(f"{method} returned an invalid JSON-RPC response")
        if "error" in payload:
            raise ObservationError(f"{method} returned a JSON-RPC error")
        response_id = payload.get("id")
        if (
            payload.get("jsonrpc") != "2.0"
            or isinstance(response_id, bool)
            or not isinstance(response_id, int)
            or response_id != request_id
        ):
            raise ObservationError(f"{method} returned an invalid JSON-RPC response")
        if "result" not in payload:
            raise ObservationError(f"{method} response is missing result")
        return payload["result"]
