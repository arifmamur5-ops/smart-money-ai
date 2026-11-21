"""API integration tests for finalized Solana slot observations."""

from datetime import datetime, timezone
import json
import unittest
from fastapi import HTTPException
from urllib.error import URLError
from urllib.request import Request
from unittest.mock import patch

from smart_money_ai.app import create_app
from smart_money_ai.config import Settings, load_settings
from smart_money_ai.solana_observation import (
    FinalizedSlotObservation,
    LiveFinalizedSlotAdapter,
    NetworkIdentity,
    ObservationError,
    ObservationSource,
)


class _Response:
    status = 200

    def __init__(self, payload: object) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class _FixedObserver:
    def __init__(self, observation: FinalizedSlotObservation) -> None:
        self.observation = observation
        self.calls = 0

    def get_finalized_slot(self) -> FinalizedSlotObservation:
        self.calls += 1
        return self.observation


def _invoke_route(application: object, path: str) -> tuple[int, dict[str, object]]:
    route = next(route for route in application.routes if getattr(route, "path", None) == path)
    try:
        response = route.endpoint()
    except HTTPException as exc:
        return exc.status_code, {"detail": exc.detail}
    return 200, json.loads(json.dumps(response))


class SolanaObservationApiTests(unittest.TestCase):
    endpoint = "https://rpc.example.invalid/path?api-key=private-token"
    genesis_hash = "expected-genesis"
    route = "/solana/observations/finalized-slot"

    def setUp(self) -> None:
        self.network = NetworkIdentity(cluster="devnet-label", genesis_hash=self.genesis_hash)
        self.observed_at = datetime(2026, 5, 6, 7, 8, 9, tzinfo=timezone.utc)
        self.observation = FinalizedSlotObservation(
            network=self.network,
            slot=321,
            commitment="finalized",
            source=ObservationSource("api-test-source"),
            observed_at=self.observed_at,
        )

    def _live_observer(self, results: list[object]) -> tuple[LiveFinalizedSlotAdapter, list[Request]]:
        requests: list[Request] = []

        def transport(request: Request, _timeout: float) -> _Response:
            requests.append(request)
            result = results.pop(0)
            if isinstance(result, BaseException):
                raise result
            return _Response(result)

        return (
            LiveFinalizedSlotAdapter(
                endpoint=self.endpoint,
                network=self.network,
                source_id="api-test-source",
                timeout=1.0,
                _transport=transport,
            ),
            requests,
        )

    @staticmethod
    def _rpc(request_id: int, result: object) -> dict[str, object]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def test_success_serializes_existing_observation_contract(self) -> None:
        observer = _FixedObserver(self.observation)
        application = create_app(Settings(), finalized_slot_observer=observer)
        api_methods = application.openapi()["paths"][self.route]

        status, body = _invoke_route(application, self.route)

        self.assertIn("get", api_methods)
        self.assertNotIn("post", api_methods)
        self.assertEqual(status, 200)
        self.assertEqual(
            body,
            {
                "network": {"cluster": "devnet-label", "genesis_hash": self.genesis_hash},
                "slot": 321,
                "commitment": "finalized",
                "source": {"source_id": "api-test-source"},
                "observed_at": "2026-05-06T07:08:09+00:00",
            },
        )
        self.assertEqual(observer.calls, 1)

    def test_missing_rpc_configuration_returns_sanitized_503(self) -> None:
        status, body = _invoke_route(create_app(Settings()), self.route)

        self.assertEqual(status, 503)
        self.assertEqual(
            body["detail"],
            {
                "code": "solana_rpc_not_configured",
                "message": "Solana RPC observation is not configured",
            },
        )

    def test_invalid_rpc_configuration_does_not_prevent_startup(self) -> None:
        invalid_settings = (
            Settings(solana_rpc_endpoint=self.endpoint),
            Settings(
                solana_rpc_endpoint="http://rpc.example.invalid/path?token=invalid-endpoint-secret",
                solana_cluster="devnet-label",
                solana_genesis_hash=self.genesis_hash,
                solana_rpc_timeout_seconds="1",
            ),
        )
        for settings in invalid_settings:
            with self.subTest(timeout=settings.solana_rpc_timeout_seconds):
                application = create_app(settings)
                status, body = _invoke_route(application, self.route)

                self.assertEqual(status, 503)
                self.assertEqual(body["detail"]["code"], "solana_rpc_configuration_invalid")
                self.assertNotIn("private-token", json.dumps(body))
                self.assertNotIn(self.endpoint, json.dumps(body))

    def test_invalid_timeout_values_are_sanitized_and_do_not_call_rpc(self) -> None:
        for timeout in ("nan", "inf", "0", "-1"):
            with self.subTest(timeout=timeout):
                settings = Settings(
                    solana_rpc_endpoint=self.endpoint,
                    solana_cluster=self.network.cluster,
                    solana_genesis_hash=self.genesis_hash,
                    solana_rpc_timeout_seconds=timeout,
                    solana_rpc_source_id="timeout-test-source",
                )
                with patch("smart_money_ai.solana_observation.live._stdlib_post") as transport:
                    application = create_app(settings)
                    transport.assert_not_called()
                    status, body = _invoke_route(application, self.route)
                    transport.assert_not_called()

                self.assertEqual(status, 503)
                self.assertEqual(
                    body["detail"]["code"],
                    "solana_rpc_configuration_invalid",
                )
                response_text = json.dumps(body)
                for configured_value in (
                    self.endpoint,
                    "private-token",
                    self.network.cluster,
                    self.genesis_hash,
                    timeout,
                    "timeout-test-source",
                ):
                    self.assertNotIn(configured_value, response_text)

    def test_transport_failure_maps_to_sanitized_502(self) -> None:
        observer, _requests = self._live_observer([URLError(self.endpoint)])
        application = create_app(Settings(), finalized_slot_observer=observer)

        status, body = _invoke_route(application, self.route)

        self.assertEqual(status, 502)
        self.assertEqual(body["detail"]["code"], "solana_observation_failed")
        self.assertNotIn("private-token", json.dumps(body))
        self.assertNotIn(self.endpoint, json.dumps(body))

    def test_network_mismatch_and_invalid_slot_map_to_sanitized_502(self) -> None:
        cases = (
            [self._rpc(1, "wrong-genesis")],
            [self._rpc(1, self.genesis_hash), self._rpc(2, True)],
        )
        for results in cases:
            with self.subTest(result_count=len(results)):
                observer, _requests = self._live_observer(results)
                status, body = _invoke_route(
                    create_app(Settings(), finalized_slot_observer=observer),
                    self.route,
                )
                self.assertEqual(status, 502)
                self.assertEqual(body["detail"]["code"], "solana_observation_failed")
                self.assertNotIn("private-token", json.dumps(body))

    def test_unexpected_observer_failure_maps_to_generic_500(self) -> None:
        sensitive_value = self.endpoint

        class BrokenObserver:
            def get_finalized_slot(self) -> FinalizedSlotObservation:
                raise RuntimeError(sensitive_value)

        status, body = _invoke_route(
            create_app(Settings(), finalized_slot_observer=BrokenObserver()),
            self.route,
        )

        self.assertEqual(status, 500)
        self.assertEqual(body["detail"]["code"], "internal_error")
        self.assertNotIn(self.endpoint, json.dumps(body))

    def test_application_creation_does_not_make_rpc_requests(self) -> None:
        settings = Settings(
            solana_rpc_endpoint=self.endpoint,
            solana_cluster=self.network.cluster,
            solana_genesis_hash=self.genesis_hash,
            solana_rpc_timeout_seconds="1.5",
        )
        with patch("smart_money_ai.solana_observation.live._stdlib_post") as transport:
            application = create_app(settings)

        self.assertEqual(application.state.solana_rpc_configuration_status, "ready")
        transport.assert_not_called()

    def test_settings_load_solana_runtime_values(self) -> None:
        settings = load_settings(
            environ={
                "SOLANA_RPC_ENDPOINT": self.endpoint,
                "SOLANA_CLUSTER": "devnet-label",
                "SOLANA_GENESIS_HASH": self.genesis_hash,
                "SOLANA_RPC_TIMEOUT_SECONDS": "2.25",
                "SOLANA_RPC_SOURCE_ID": "configured-source",
            },
            env_file=None,
        )

        self.assertEqual(settings.solana_rpc_endpoint, self.endpoint)
        self.assertEqual(settings.solana_cluster, "devnet-label")
        self.assertEqual(settings.solana_genesis_hash, self.genesis_hash)
        self.assertEqual(settings.solana_rpc_timeout_seconds, "2.25")
        self.assertEqual(settings.solana_rpc_source_id, "configured-source")


if __name__ == "__main__":
    unittest.main()
