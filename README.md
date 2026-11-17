# Smart Money AI

Smart Money AI is being developed as a generic platform foundation. Session 1 covers repository and engineering foundations, monorepo structure and module boundaries, secure development configuration, architecture documentation and ADRs, generic application/platform foundations, storage and event design, and local validation and engineering workflow.

Session 1 does not include provider selection or a Solana observation pipeline, wallet/whale/token analysis, trading, prediction, live execution, or AI/domain-agent implementation. Solana remains a target for a later domain phase; Helius has not been selected.

## Project status

- **Planned:** Python, FastAPI, PostgreSQL, NATS JetStream, Docker Engine and Docker Compose, Make, and Git. **Selected:** uv for Python environment and dependency management; `pyproject.toml` defines project metadata for Python `>=3.12,<3.15`. No application dependencies or `uv.lock` are present, and this does not mean dependencies are installed or the application runs.
- **Documented:** the architecture direction and design decisions are recorded in the [Session 1 baseline](docs/engineering/session-1-baseline.md) and [ADRs](docs/adr/).
- **Present in worktree:** the current worktree contains documentation, configuration templates, and directory scaffolding, but no application functionality or infrastructure has been implemented. In particular, there is no API, database schema or migration, NATS deployment, worker, or Docker Compose stack.

## Repository structure

Project directories and files currently present:

```text
.
├── .env.example
├── .gitignore
├── README.md
├── pyproject.toml
├── apps/
│   └── api/                         # empty scaffold
├── docs/
│   ├── adr/
│   │   ├── 0001-modular-monolith.md
│   │   ├── 0002-postgresql-source-of-truth.md
│   │   └── 0003-event-first-design.md
│   └── engineering/
│       └── session-1-baseline.md
├── infra/
│   └── docker/                      # empty scaffold
├── migrations/                      # empty scaffold
├── packages/                        # empty scaffold
├── services/                        # empty scaffold
└── tests/                           # empty scaffold
```

The workspace also has empty `.agents/`, `.aws/`, and `.codex/` directories; they are not application or platform components. Directory names describe repository organization and do not, by themselves, establish module contracts or implementation.

## Development configuration

`.env.example` is a development template; its settings are not consumed by application code yet. Keep real credentials in a local `.env` file and out of version control.
