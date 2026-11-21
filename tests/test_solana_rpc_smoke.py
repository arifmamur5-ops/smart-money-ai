"""Offline tests for smoke-check configuration and safe output."""

from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import unittest
from unittest.mock import patch

from scripts.solana_rpc_smoke import main
from smart_money_ai.config import Settings, load_settings
from smart_money_ai.solana_observation import (
    FinalizedSlotObservation,
    NetworkIdentity,
    ObservationSource,
)


class SolanaRpcSmokeTests(unittest.TestCase):
    endpoint = "https://rpc.example.invalid/path?api-key=private-token"

    def test_missing_configuration_returns_without_constructing_adapter(self) -> None:
        output = StringIO()
        with patch("scripts.solana_rpc_smoke.LiveFinalizedSlotAdapter") as adapter:
            with redirect_stdout(output):
                status = main(Settings())

        self.assertEqual(status, 2)
        adapter.assert_not_called()
        self.assertNotIn(self.endpoint, output.getvalue())
        self.assertIn("SOLANA_RPC_TIMEOUT_SECONDS", output.getvalue())

    def test_canonical_environment_names_and_application_default_are_used(self) -> None:
        settings = load_settings(
            environ={
                "SOLANA_RPC_ENDPOINT": self.endpoint,
                "SOLANA_CLUSTER": "devnet",
                "SOLANA_GENESIS_HASH": "expected-genesis",
                "SOLANA_RPC_TIMEOUT_SECONDS": "2.5",
            },
            env_file=None,
        )
        observation = FinalizedSlotObservation(
            network=NetworkIdentity("devnet", "expected-genesis"),
            slot=42,
            commitment="finalized",
            source=ObservationSource("application-rpc"),
            observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        output = StringIO()
        with patch("scripts.solana_rpc_smoke.LiveFinalizedSlotAdapter") as adapter_class:
            adapter_class.return_value.get_finalized_slot.return_value = observation
            with redirect_stdout(output):
                status = main(settings)

        self.assertEqual(status, 0)
        adapter_class.assert_called_once_with(
            endpoint=self.endpoint,
            network=NetworkIdentity("devnet", "expected-genesis"),
            source_id="application-rpc",
            timeout=2.5,
        )
        self.assertNotIn(self.endpoint, output.getvalue())
        self.assertNotIn("private-token", output.getvalue())

    def test_legacy_timeout_and_source_names_are_not_used(self) -> None:
        settings = load_settings(
            environ={
                "SOLANA_RPC_ENDPOINT": self.endpoint,
                "SOLANA_CLUSTER": "devnet",
                "SOLANA_GENESIS_HASH": "expected-genesis",
                "SOLANA_RPC_TIMEOUT": "2.5",
                "SOLANA_SOURCE_ID": "legacy-source",
            },
            env_file=None,
        )
        output = StringIO()
        with patch("scripts.solana_rpc_smoke.LiveFinalizedSlotAdapter") as adapter:
            with redirect_stdout(output):
                status = main(settings)

        self.assertEqual(status, 2)
        adapter.assert_not_called()
        self.assertIn("SOLANA_RPC_TIMEOUT_SECONDS", output.getvalue())


if __name__ == "__main__":
    unittest.main()
