"""Deterministic tests for the live adapter's HTTP transport boundary."""

from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from unittest import TestCase
from urllib.error import HTTPError, URLError
from urllib.request import Request

from smart_money_ai.solana_observation import (
    FinalizedSlotObservation,
    LiveFinalizedSlotAdapter,
    NetworkIdentity,
    ObservationError,
)
from smart_money_ai.solana_observation.live import (
    _MAX_RPC_RESPONSE_BYTES,
    _NoRedirectHandler,
    _RedirectRejected,
)


class _Response:
    def __init__(
        self,
        payload: object,
        status: int = 200,
        *,
        content_length: str | None = None,
    ) -> None:
        self.status = status
        if isinstance(payload, bytes):
            self._body = payload
        else:
            self._body = json.dumps(payload).encode("utf-8")
        self.headers = {} if content_length is None else {"Content-Length": content_length}
        self.closed = False
        self.read_sizes: list[int] = []

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        self.closed = True
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if size < 0:
            size = len(self._body)
        chunk, self._body = self._body[:size], self._body[size:]
        return chunk


class _TrackedBody(BytesIO):
    def __init__(self, payload: bytes, *, fail_on_close: bool = False) -> None:
        super().__init__(payload)
        self.close_called = False
        self.fail_on_close = fail_on_close

    def close(self) -> None:
        self.close_called = True
        super().close()
        if self.fail_on_close:
            raise OSError("private cleanup detail")


class LiveFinalizedSlotAdapterTests(TestCase):
    endpoint = "https://rpc.example.invalid/path?api-key=private-token"
    genesis = "configured-genesis"

    def setUp(self) -> None:
        self.network = NetworkIdentity(cluster="configured-label", genesis_hash=self.genesis)
        self.calls: list[tuple[Request, float]] = []

    def adapter(self, responses: list[object], **kwargs: object) -> LiveFinalizedSlotAdapter:
        def transport(request: Request, timeout: float) -> _Response:
            self.calls.append((request, timeout))
            response = responses.pop(0)
            if isinstance(response, BaseException):
                raise response
            if isinstance(response, _Response):
                return response
            return _Response(response)

        options: dict[str, object] = {
            "endpoint": self.endpoint,
            "network": self.network,
            "source_id": "neutral-source",
            "timeout": 2.5,
            "_transport": transport,
        }
        options.update(kwargs)
        return LiveFinalizedSlotAdapter(**options)  # type: ignore[arg-type]

    @staticmethod
    def rpc(result: object, request_id: int, **extra: object) -> dict[str, object]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result, **extra}

    def test_redirect_handler_rejects_redirect_request(self) -> None:
        request = Request(self.endpoint, data=b"request", method="POST")
        handler = _NoRedirectHandler()
        response_file = _TrackedBody(b"redirect response body")

        with self.assertRaises(_RedirectRejected):
            handler.redirect_request(
                request,
                response_file,
                307,
                "Temporary Redirect",
                {},
                "https://redirect.example.invalid/target",
            )
        self.assertTrue(response_file.close_called)

    def test_redirect_cleanup_failure_does_not_replace_redirect_rejection(self) -> None:
        request = Request(self.endpoint, data=b"request", method="POST")
        handler = _NoRedirectHandler()
        response_file = _TrackedBody(b"redirect response body", fail_on_close=True)

        with self.assertRaises(_RedirectRejected):
            handler.redirect_request(
                request,
                response_file,
                307,
                "Temporary Redirect",
                {},
                "https://redirect.example.invalid/target",
            )

        self.assertTrue(response_file.close_called)

    def test_adapter_maps_redirect_rejection_without_exposing_endpoint(self) -> None:
        adapter = self.adapter([_RedirectRejected()])

        with self.assertRaises(ObservationError) as raised:
            adapter.get_finalized_slot()

        self.assertIn("redirect was rejected", str(raised.exception))
        self.assertNotIn(self.endpoint, str(raised.exception))
        self.assertNotIn("private-token", str(raised.exception))
        self.assertEqual(len(self.calls), 1)

    def test_success_verifies_network_then_requests_finalized_slot(self) -> None:
        offset_time = datetime(2026, 2, 3, 9, 30, tzinfo=timezone(timedelta(hours=7)))
        adapter = self.adapter(
            [self.rpc(self.genesis, 1), self.rpc(1234, 2)],
            clock=lambda: offset_time,
        )

        observation = adapter.get_finalized_slot()

        self.assertIsInstance(observation, FinalizedSlotObservation)
        self.assertEqual(observation.network, self.network)
        self.assertEqual(observation.network.cluster, "configured-label")
        self.assertEqual(observation.source.source_id, "neutral-source")
        self.assertEqual(observation.slot, 1234)
        self.assertEqual(observation.commitment, "finalized")
        self.assertEqual(observation.observed_at, datetime(2026, 2, 3, 2, 30, tzinfo=timezone.utc))
        self.assertEqual([json.loads(request.data or b"")["method"] for request, _ in self.calls], ["getGenesisHash", "getSlot"])
        self.assertEqual(json.loads(self.calls[0][0].data or b"")["params"], [])
        self.assertEqual(json.loads(self.calls[1][0].data or b"")["params"], [{"commitment": "finalized"}])
        self.assertEqual([timeout for _, timeout in self.calls], [2.5, 2.5])

    def test_genesis_mismatch_stops_before_slot_call(self) -> None:
        adapter = self.adapter([self.rpc("other-genesis", 1), self.rpc(10, 2)])
        with self.assertRaisesRegex(ObservationError, "did not match"):
            adapter.get_finalized_slot()
        self.assertEqual(len(self.calls), 1)

    def test_genesis_result_must_be_nonempty_string(self) -> None:
        for result in ("", "  ", 42, None):
            with self.subTest(result=result):
                adapter = self.adapter([self.rpc(result, 1)])
                with self.assertRaises(ObservationError):
                    adapter.get_finalized_slot()

    def test_slot_must_be_u64_integer_not_bool(self) -> None:
        for slot in (-1, True, 1.5, "10", 1 << 64):
            with self.subTest(slot=slot):
                adapter = self.adapter([self.rpc(self.genesis, 1), self.rpc(slot, 2)])
                with self.assertRaises(ObservationError):
                    adapter.get_finalized_slot()

    def test_u64_boundaries_are_accepted(self) -> None:
        for slot in (0, (1 << 64) - 1):
            with self.subTest(slot=slot):
                adapter = self.adapter([self.rpc(self.genesis, 1), self.rpc(slot, 2)])
                self.assertEqual(adapter.get_finalized_slot().slot, slot)

    def test_protocol_failures_are_mapped_to_observation_error(self) -> None:
        cases = (
            (b"{", "invalid JSON"),
            ({"jsonrpc": "2.0", "id": True, "result": self.genesis}, "invalid JSON-RPC"),
            (self.rpc(self.genesis, 9), "invalid JSON-RPC"),
            ({"jsonrpc": "1.0", "id": 1, "result": self.genesis}, "invalid JSON-RPC"),
            ({"jsonrpc": "2.0", "id": 1}, "missing result"),
            ({"jsonrpc": "2.0", "id": 1, "result": self.genesis, "error": {"code": 1}}, "JSON-RPC error"),
        )
        for payload, reason in cases:
            with self.subTest(reason=reason):
                response = _Response(payload)
                adapter = self.adapter([response])
                with self.assertRaisesRegex(ObservationError, reason):
                    adapter.get_finalized_slot()
                self.assertTrue(response.closed)

    def test_raw_response_body_is_not_exposed(self) -> None:
        secret_body = b"provider response contains private-token and account details"
        adapter = self.adapter([_Response(secret_body)])
        with self.assertRaises(ObservationError) as raised:
            adapter.get_finalized_slot()
        self.assertNotIn("private-token", str(raised.exception))
        self.assertNotIn("account details", str(raised.exception))

    def test_http_error_body_is_closed_and_mapped_without_sensitive_details(self) -> None:
        raw_body = b"provider returned private-token Authorization: Bearer secret-value"
        response_file = _TrackedBody(raw_body)
        failure = HTTPError(
            self.endpoint,
            500,
            f"transport detail private-token {raw_body.decode()}",
            {},
            response_file,
        )
        adapter = self.adapter([failure])

        with self.assertRaises(ObservationError) as raised:
            adapter.get_finalized_slot()

        self.assertEqual(str(raised.exception), "getGenesisHash returned an HTTP error")
        self.assertTrue(response_file.close_called)
        for sensitive in (self.endpoint, "private-token", "Authorization", "secret-value", raw_body.decode()):
            self.assertNotIn(sensitive, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)

    def test_http_error_cleanup_failure_does_not_replace_sanitized_transport_error(self) -> None:
        response_file = _TrackedBody(b"private response", fail_on_close=True)
        failure = HTTPError(self.endpoint, 500, "private transport detail", {}, response_file)
        adapter = self.adapter([failure])

        with self.assertRaises(ObservationError) as raised:
            adapter.get_finalized_slot()

        self.assertEqual(str(raised.exception), "getGenesisHash returned an HTTP error")
        self.assertTrue(response_file.close_called)
        self.assertNotIn(self.endpoint, str(raised.exception))
        self.assertNotIn("private", str(raised.exception))

    def test_normal_http_status_rejection_closes_response(self) -> None:
        response = _Response(b"private error body", status=503)
        adapter = self.adapter([response])

        with self.assertRaisesRegex(ObservationError, "HTTP error"):
            adapter.get_finalized_slot()

        self.assertTrue(response.closed)

    def test_malformed_json_response_is_closed(self) -> None:
        response = _Response(b"{")
        adapter = self.adapter([response])

        with self.assertRaisesRegex(ObservationError, "invalid JSON"):
            adapter.get_finalized_slot()

        self.assertTrue(response.closed)

    def test_response_within_size_limit_is_accepted_and_closed(self) -> None:
        genesis_response = _Response(self.rpc(self.genesis, 1))
        slot_response = _Response(self.rpc(1234, 2))
        adapter = self.adapter([genesis_response, slot_response])

        observation = adapter.get_finalized_slot()

        self.assertEqual(observation.slot, 1234)
        for response in (genesis_response, slot_response):
            self.assertTrue(response.closed)
            self.assertEqual(response.read_sizes, [_MAX_RPC_RESPONSE_BYTES + 1])

    def test_oversized_response_is_rejected_and_closed_without_trusting_content_length(self) -> None:
        for content_length in (None, "1"):
            with self.subTest(content_length=content_length):
                response = _Response(
                    b"x" * (_MAX_RPC_RESPONSE_BYTES + 1),
                    content_length=content_length,
                )
                adapter = self.adapter([response])

                with self.assertRaisesRegex(ObservationError, "maximum permitted size") as raised:
                    adapter.get_finalized_slot()

                self.assertTrue(response.closed)
                self.assertEqual(response.read_sizes, [_MAX_RPC_RESPONSE_BYTES + 1])
                self.assertNotIn(self.endpoint, str(raised.exception))
                self.assertNotIn("private-token", str(raised.exception))
                self.assertNotIn("x" * 100, str(raised.exception))

    def test_http_redirect_and_transport_failures_are_safe(self) -> None:
        for failure in (
            URLError(self.endpoint),
            TimeoutError(self.endpoint),
            HTTPError(self.endpoint, 302, "redirect", {}, None),
            _Response({}, status=503),
        ):
            with self.subTest(failure=type(failure).__name__):
                adapter = self.adapter([failure])
                with self.assertRaises(ObservationError) as raised:
                    adapter.get_finalized_slot()
                self.assertNotIn(self.endpoint, str(raised.exception))
                self.assertNotIn("private-token", str(raised.exception))

    def test_invalid_endpoint_timeout_network_and_source_are_rejected(self) -> None:
        for endpoint in ("http://host/path", "https:///missing-host"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                self.adapter([], endpoint=endpoint)
        for timeout in (0, -1, float("inf"), float("nan"), 10**10000):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                self.adapter([], timeout=timeout)
        with self.assertRaises(TypeError):
            self.adapter([], network="devnet")
        for source_id in ("", " "):
            with self.subTest(source_id=source_id), self.assertRaises(ValueError):
                self.adapter([], source_id=source_id)

    def test_invalid_clock_is_an_observation_error(self) -> None:
        for clock in (
            lambda: datetime(2026, 1, 1),
            lambda: "invalid",
            lambda: (_ for _ in ()).throw(RuntimeError(self.endpoint)),
        ):
            adapter = self.adapter([self.rpc(self.genesis, 1), self.rpc(1, 2)], clock=clock)
            with self.assertRaises(ObservationError) as raised:
                adapter.get_finalized_slot()
            self.assertNotIn("private-token", str(raised.exception))
            self.assertIsNone(raised.exception.__cause__)

    def test_genesis_transport_failure_does_not_request_slot(self) -> None:
        adapter = self.adapter([OSError(self.endpoint)])
        with self.assertRaises(ObservationError):
            adapter.get_finalized_slot()
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    import unittest

    unittest.main()
