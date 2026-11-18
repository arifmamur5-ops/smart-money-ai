"""ASGI application entrypoint."""

from smart_money_ai.app import create_app

app = create_app()
