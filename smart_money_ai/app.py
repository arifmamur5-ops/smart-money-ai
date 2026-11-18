"""FastAPI application factory and application wiring."""

from fastapi import FastAPI

from smart_money_ai.config import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the HTTP application with validated runtime settings."""
    runtime_settings = settings if settings is not None else load_settings()
    application = FastAPI(title=runtime_settings.app_name)
    application.state.settings = runtime_settings

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Report that the application process can serve requests."""
        return {"status": "ok"}

    return application
