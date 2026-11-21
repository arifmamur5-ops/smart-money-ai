"""Tests for provider-neutral finalized slot observation models and fake adapter."""

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

from smart_money_ai.solana_observation import (
    FakeSolanaObservationAdapter,
    FinalizedSlotObservation,
    FinalizedSlotObserver,
    NetworkIdentity,
    ObservationError,
    ObservationSource,
)


class NetworkIdentityTests(unittest.TestCase):
    def test_accepts_cluster_and_genesis_hash(self) -> None:
        identity = NetworkIdentity(cluster="devnet", genesis_hash="genesis-123")

        self.assertEqual(identity.cluster, "devnet")
        self.assertEqual(identity.genesis_hash, "genesis-123")

    def test_rejects_empty_or_whitespace_cluster(self) -> None:
        for cluster in ("", "   "):
            with self.subTest(cluster=cluster):
                with self.assertRaises(ValueError):
                    NetworkIdentity(cluster=cluster, genesis_hash="genesis-123")

    def test_rejects_empty_or_whitespace_genesis_hash(self) -> None:
        for genesis_hash in ("", " \t "):
            with self.subTest(genesis_hash=genesis_hash):
                with self.assertRaises(ValueError):
                    NetworkIdentity(cluster="devnet", genesis_hash=genesis_hash)

    def test_rejects_non_string_fields(self) -> None:
        with self.assertRaises(TypeError):
            NetworkIdentity(cluster=1, genesis_hash="genesis-123")  # type: ignore[arg-type]


class ObservationSourceTests(unittest.TestCase):
    def test_accepts_source_id(self) -> None:
        source = ObservationSource(source_id="test-source")

        self.assertEqual(source.source_id, "test-source")

    def test_rejects_empty_or_whitespace_source_id(self) -> None:
        for source_id in ("", " \t "):
            with self.subTest(source_id=source_id):
                with self.assertRaises(ValueError):
                    ObservationSource(source_id=source_id)

    def test_rejects_non_string_source_id(self) -> None:
        with self.assertRaises(TypeError):
            ObservationSource(source_id=3)  # type: ignore[arg-type]


class FinalizedSlotObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = NetworkIdentity(cluster="devnet", genesis_hash="genesis-123")
        self.source = ObservationSource(source_id="test-source")
        self.observed_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    def make_observation(self, **overrides: object) -> FinalizedSlotObservation:
        values: dict[str, object] = {
            "network": self.network,
            "slot": 0,
            "commitment": "finalized",
            "source": self.source,
            "observed_at": self.observed_at,
        }
        values.update(overrides)
        return FinalizedSlotObservation(**values)  # type: ignore[arg-type]

    def test_accepts_valid_finalized_observation_and_zero_slot(self) -> None:
        observation = self.make_observation()

        self.assertEqual(observation.slot, 0)
        self.assertEqual(observation.commitment, "finalized")

    def test_accepts_maximum_uint64_slot(self) -> None:
        observation = self.make_observation(slot=(1 << 64) - 1)

        self.assertEqual(observation.slot, (1 << 64) - 1)

    def test_rejects_negative_boolean_and_non_integer_slots(self) -> None:
        for slot, error in ((-1, ValueError), (True, TypeError), (1.5, TypeError)):
            with self.subTest(slot=slot):
                with self.assertRaises(error):
                    self.make_observation(slot=slot)

    def test_rejects_slot_above_uint64_maximum(self) -> None:
        with self.assertRaises(ValueError):
            self.make_observation(slot=1 << 64)

    def test_rejects_non_finalized_commitment(self) -> None:
        with self.assertRaises(ValueError):
            self.make_observation(commitment="confirmed")

    def test_rejects_invalid_network_and_source_types(self) -> None:
        with self.assertRaises(TypeError):
            self.make_observation(network="devnet")
        with self.assertRaises(TypeError):
            self.make_observation(source="test-source")

    def test_rejects_naive_datetime(self) -> None:
        with self.assertRaises(ValueError):
            self.make_observation(observed_at=datetime(2026, 1, 2, 3, 4, 5))

    def test_normalizes_observed_at_to_utc(self) -> None:
        offset_time = datetime(
            2026, 1, 2, 5, 4, 5, tzinfo=timezone(timedelta(hours=2))
        )

        observation = self.make_observation(observed_at=offset_time)

        self.assertEqual(observation.observed_at, self.observed_at)
        self.assertIs(observation.observed_at.tzinfo, timezone.utc)

    def test_model_is_immutable(self) -> None:
        observation = self.make_observation()

        with self.assertRaises(FrozenInstanceError):
            observation.slot = 10  # type: ignore[misc]


class FakeSolanaObservationAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = NetworkIdentity(cluster="devnet", genesis_hash="genesis-123")
        self.source = ObservationSource(source_id="local-fake")

    def test_returns_configured_observation_and_implements_protocol(self) -> None:
        observed_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        adapter = FakeSolanaObservationAdapter(
            network=self.network,
            slot=42,
            source=self.source,
            clock=lambda: observed_at,
        )

        observer: FinalizedSlotObserver = adapter
        observation = observer.get_finalized_slot()

        self.assertEqual(observation.network, self.network)
        self.assertEqual(observation.slot, 42)
        self.assertEqual(observation.source, self.source)
        self.assertEqual(observation.observed_at, observed_at)

    def test_default_source_identity_is_fake(self) -> None:
        adapter = FakeSolanaObservationAdapter(
            network=self.network,
            slot=42,
            clock=lambda: datetime(2026, 1, 2, tzinfo=timezone.utc),
        )

        self.assertEqual(adapter.get_finalized_slot().source.source_id, "fake")

    def test_uses_injected_clock_for_deterministic_timestamp_results(self) -> None:
        timestamps = iter(
            (
                datetime(2026, 1, 2, 3, tzinfo=timezone.utc),
                datetime(2026, 1, 2, 4, tzinfo=timezone.utc),
            )
        )
        adapter = FakeSolanaObservationAdapter(
            network=self.network,
            slot=42,
            clock=lambda: next(timestamps),
        )

        first = adapter.get_finalized_slot()
        second = adapter.get_finalized_slot()

        self.assertEqual(first.observed_at, datetime(2026, 1, 2, 3, tzinfo=timezone.utc))
        self.assertEqual(second.observed_at, datetime(2026, 1, 2, 4, tzinfo=timezone.utc))

    def test_rejects_naive_or_invalid_clock_results(self) -> None:
        for clock, error in (
            (lambda: datetime(2026, 1, 2, 3), ValueError),
            (lambda: "not a datetime", TypeError),
        ):
            with self.subTest(error=error):
                adapter = FakeSolanaObservationAdapter(
                    network=self.network,
                    slot=42,
                    clock=clock,  # type: ignore[arg-type]
                )
                with self.assertRaises(error):
                    adapter.get_finalized_slot()

    def test_simulated_failure_raises_observation_error(self) -> None:
        adapter = FakeSolanaObservationAdapter(
            network=self.network,
            slot=42,
            clock=lambda: datetime(2026, 1, 2, tzinfo=timezone.utc),
            fail=True,
        )

        with self.assertRaises(ObservationError):
            adapter.get_finalized_slot()


if __name__ == "__main__":
    unittest.main()
