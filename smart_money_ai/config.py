"""Runtime configuration loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


_DEFAULT_APP_NAME = "Smart Money AI"
_DEFAULT_APP_ENV = Environment.DEVELOPMENT
_DEFAULT_LOG_LEVEL = LogLevel.INFO


class ConfigurationError(ValueError):
    """Raised when runtime configuration is invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = _DEFAULT_APP_NAME
    environment: Environment = _DEFAULT_APP_ENV
    log_level: LogLevel = _DEFAULT_LOG_LEVEL


def load_settings(
    *,
    environ: Mapping[str, str] | None = None,
    env_file: str | Path | None = ".env",
) -> Settings:
    """Load settings from a local dotenv file, overridden by process environment.

    Pass ``env_file=None`` to disable dotenv loading. ``environ`` and ``env_file``
    can be supplied explicitly by callers that need a controlled configuration
    source, such as tests.
    """
    values: dict[str, str | None] = {}
    if env_file is not None:
        values.update(dotenv_values(Path(env_file)))
    values.update(os.environ if environ is None else environ)

    app_name_value = values.get("APP_NAME")
    app_name = (_DEFAULT_APP_NAME if app_name_value is None else app_name_value).strip()
    if not app_name:
        raise ConfigurationError("APP_NAME must not be empty")

    try:
        environment_value = values.get("APP_ENV")
        environment = Environment(
            (_DEFAULT_APP_ENV.value if environment_value is None else environment_value).strip()
        )
    except ValueError as exc:
        allowed = ", ".join(item.value for item in Environment)
        raise ConfigurationError(f"APP_ENV must be one of: {allowed}") from exc

    try:
        log_level_value = values.get("LOG_LEVEL")
        log_level = LogLevel(
            (_DEFAULT_LOG_LEVEL.value if log_level_value is None else log_level_value)
            .strip()
            .upper()
        )
    except ValueError as exc:
        allowed = ", ".join(item.value for item in LogLevel)
        raise ConfigurationError(f"LOG_LEVEL must be one of: {allowed}") from exc

    return Settings(app_name=app_name, environment=environment, log_level=log_level)
