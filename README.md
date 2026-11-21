# Smart Money AI

Smart Money AI is an on-chain intelligence and research application. The project is being built as a Python modular monolith, with domain data quality, provenance, reproducibility, and a small local development footprint as priorities.

## Project status

### Implemented

- Typed runtime settings for application name, environment, and log level. Settings load from `.env` and process environment variables; process environment values take precedence.
- FastAPI application factory at `smart_money_ai.app:create_app` and ASGI entrypoint at `smart_money_ai.main:app`.
- `GET /health`, which confirms the application can respond. It does not check dependency readiness.
- Provider-neutral, read-only finalized Solana slot observation through the M1 fake and M5 HTTPS JSON-RPC adapter. The live adapter verifies genesis identity on each observation and has not been validated against a live endpoint.
- `GET /solana/observations/finalized-slot`, which explicitly requests and returns one finalized slot observation when RPC configuration is valid.
- Offline, researcher-curated Smart Wallet Dataset domain contracts and deterministic snapshot/digest construction. No wallet data is collected by this capability.
- Local developer commands through the Makefile, using uv and the committed lockfile.

### Planned

- PostgreSQL as the planned platform source of truth, subject to concrete data and persistence requirements.
- NATS JetStream, Docker Engine, and Docker Compose remain technology directions for future needs.
- On-chain observation, provenance, wallet/token intelligence, research/replay, and risk capabilities belong to future gated domain phases.

### Not implemented

- Database connections, schemas, or migrations.
- Message broker integration, workers, or a Docker/Compose application stack.
- Provider selection or live endpoint verification, wallet/token analysis, trading/execution, or AI agents.
- Production deployment or production readiness guarantees.

Generic task lifecycle, workflow orchestration, policy, audit integrity, retry/recovery, and outbox infrastructure belong to the separate Swarm Forge project. Smart Money AI does not duplicate those capabilities and is not integrated with Swarm Forge.

## Requirements

- Python `>=3.12,<3.15`
- [uv](https://docs.astral.sh/uv/) for environment and dependency management
- GNU Make

Runtime dependencies are FastAPI, python-dotenv, and Uvicorn. Exact resolved dependency versions are recorded in `uv.lock`. No database, broker, or container runtime is needed for the current application.

The live finalized-slot adapter uses Python's standard library and adds no dependency. See the [M5 adapter notes](docs/engineering/live-finalized-slot-adapter.md) for constructor requirements and the opt-in manual smoke check.

## Local development

From the repository root, synchronize the environment:

```sh
make sync
```

Optionally copy `.env.example` to `.env` and adjust `APP_NAME`, `APP_ENV`, or `LOG_LEVEL`. The defaults are suitable for local development; `.env` is ignored by Git. To enable finalized-slot observations, also set `SOLANA_RPC_ENDPOINT`, `SOLANA_CLUSTER`, `SOLANA_GENESIS_HASH`, and `SOLANA_RPC_TIMEOUT_SECONDS`. These values are optional as a group; without them, the app starts normally and the observation endpoint returns HTTP 503. See the [Solana observation API notes](docs/engineering/solana-observation-api.md) for details.

Start the application:

```sh
make run
```

The server binds to `127.0.0.1:8000` by default. If that port is occupied, override it, for example with `make run PORT=8001`. Check the process health endpoint in another terminal:

```sh
curl --fail http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

The health response only means the application process handled the request. It makes no claim about database, broker, or other infrastructure readiness.

The finalized-slot API performs its RPC reads only when requested. It returns configured network identity, slot, finalized commitment, source ID, and local `observed_at` receipt time; it does not return or infer a Solana block timestamp.

The Smart Wallet Dataset package currently supports offline seed registration, provenance references, conservative optional activity facts, and reproducible finite snapshots. It does not query RPC history, store snapshots, or establish historical activity completeness. See the [dataset domain contract](docs/engineering/smart-wallet-dataset.md).

## Tests and checks

Run the test suite:

```sh
make test
```

Validate lockfile consistency:

```sh
make lock-check
```

Run both checks:

```sh
make check
```

`make check` runs the lockfile check and unit tests. Each target returns a non-zero exit status if its command fails.

## Repository layout

```text
.
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── pyproject.toml
├── uv.lock
├── smart_money_ai/
│   ├── __init__.py
│   ├── app.py                 # application factory, health, and observation routes
│   ├── config.py              # typed runtime settings and validation
│   ├── main.py                # ASGI entrypoint
│   ├── solana_observation/    # provider-neutral observation models and adapters
│   └── wallet_dataset/       # offline dataset contracts and deterministic snapshots
├── tests/
│   ├── test_app.py
│   ├── test_config.py
│   ├── test_solana_api.py
│   ├── test_solana_observation.py
│   ├── test_solana_live_observation.py
│   ├── test_solana_rpc_smoke.py
│   └── test_wallet_dataset.py
├── scripts/
│   └── solana_rpc_smoke.py    # manual opt-in live check; not test discovery
├── docs/
│   ├── adr/                   # accepted architecture decisions
│   └── engineering/           # baseline, ownership, and domain contracts
├── apps/api/                  # empty scaffold
├── infra/docker/              # empty scaffold
├── migrations/                # empty scaffold
├── packages/                  # empty scaffold
└── services/                  # empty scaffold
```

The empty scaffold directories do not imply implemented services or deployment boundaries. See the [Session 1 baseline](docs/engineering/session-1-baseline.md), [capability ownership boundaries](docs/engineering/capability-ownership.md), and [ADRs](docs/adr/) for design decisions and open questions.
