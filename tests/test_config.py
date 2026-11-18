"""Focused tests for runtime configuration."""

import tempfile
import unittest
from pathlib import Path

from smart_money_ai.config import (
    ConfigurationError,
    Environment,
    LogLevel,
    Settings,
    load_settings,
)


class LoadSettingsTests(unittest.TestCase):
    def test_defaults_without_environment_or_dotenv(self) -> None:
        self.assertEqual(load_settings(environ={}, env_file=None), Settings())

    def test_environment_overrides(self) -> None:
        settings = load_settings(
            environ={
                "APP_NAME": "Research Lab",
                "APP_ENV": "test",
                "LOG_LEVEL": "debug",
            },
            env_file=None,
        )

        self.assertEqual(settings.app_name, "Research Lab")
        self.assertIs(settings.environment, Environment.TEST)
        self.assertIs(settings.log_level, LogLevel.DEBUG)

    def test_invalid_environment_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "APP_ENV must be one of"):
            load_settings(environ={"APP_ENV": "staging"}, env_file=None)

    def test_invalid_log_level_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "LOG_LEVEL must be one of"):
            load_settings(environ={"LOG_LEVEL": "TRACE"}, env_file=None)

    def test_blank_app_name_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "APP_NAME must not be empty"):
            load_settings(environ={"APP_NAME": "   "}, env_file=None)

    def test_dotenv_is_loaded_and_process_environment_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                'APP_NAME="From file"\nAPP_ENV=production\nLOG_LEVEL=WARNING\n',
                encoding="utf-8",
            )

            settings = load_settings(
                environ={"APP_ENV": "test"},
                env_file=env_path,
            )

        self.assertEqual(settings.app_name, "From file")
        self.assertIs(settings.environment, Environment.TEST)
        self.assertIs(settings.log_level, LogLevel.WARNING)


if __name__ == "__main__":
    unittest.main()
