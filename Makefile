UV_BIN ?= uv
PORT ?= 8000

.PHONY: sync run test lock-check check

sync:
	$(UV_BIN) sync --locked

run:
	$(UV_BIN) run --locked uvicorn smart_money_ai.main:app --host 127.0.0.1 --port $(PORT)

test:
	$(UV_BIN) run --locked python -m unittest discover -s tests -v

lock-check:
	$(UV_BIN) lock --check

check: lock-check test
