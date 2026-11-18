"""Focused tests for application initialization and health behavior."""

import asyncio
import json
import unittest
from unittest.mock import patch

from smart_money_ai.app import create_app
from smart_money_ai.config import Environment, LogLevel, Settings


class CreateAppTests(unittest.TestCase):
    def test_factory_wires_supplied_settings(self) -> None:
        settings = Settings(
            app_name="Research Service",
            environment=Environment.TEST,
            log_level=LogLevel.DEBUG,
        )

        application = create_app(settings)

        self.assertEqual(application.title, "Research Service")
        self.assertIs(application.state.settings, settings)

    def test_factory_loads_settings_when_not_supplied(self) -> None:
        settings = Settings(app_name="Loaded Settings")
        with patch("smart_money_ai.app.load_settings", return_value=settings) as load:
            application = create_app()

        load.assert_called_once_with()
        self.assertIs(application.state.settings, settings)

    def test_health_reports_process_response_without_readiness_claim(self) -> None:
        application = create_app(Settings())
        messages: list[dict[str, object]] = []
        request_received = False

        async def receive() -> dict[str, object]:
            nonlocal request_received
            if not request_received:
                request_received = True
                return {"type": "http.request", "body": b"", "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message: dict[str, object]) -> None:
            messages.append(message)

        scope: dict[str, object] = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/health",
            "raw_path": b"/health",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"test")],
            "client": ("test", 123),
            "server": ("test", 80),
        }

        asyncio.run(application(scope, receive, send))

        response_start = next(
            message for message in messages if message["type"] == "http.response.start"
        )
        response_body = next(
            message for message in messages if message["type"] == "http.response.body"
        )
        self.assertEqual(response_start["status"], 200)
        self.assertEqual(json.loads(response_body["body"]), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
