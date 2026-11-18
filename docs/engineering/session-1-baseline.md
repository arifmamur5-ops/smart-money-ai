# Session 1 Engineering Baseline

**Phase:** Session 1 — Repository Foundation
**Reference:** Smart Money AI Master Dossier v1.2, Sections 5.1–5.4 and 17.2, 17.4–17.6, based on the project context supplied for this work.
**Document status:** Records accepted direction, discussed design concepts, current repository evidence, and open work. It does not declare the foundation complete.

## Purpose and active scope

Session 1 establishes a generic platform foundation, not a blockchain or financial-domain implementation. Its seven scope areas are:

1. Repository and engineering foundation.
2. Monorepo structure and module boundaries.
3. Secure development configuration.
4. Architecture documentation and ADRs.
5. Generic application/platform foundation.
6. Storage and event architecture decisions at the design level.
7. Local validation and engineering workflow.

The presence of a planned component, directory, configuration template, or design note does not mean that application behavior or infrastructure has been implemented or is running.

## Out of scope for Session 1

- Selecting or binding to a specific on-chain provider.
- A Solana observation pipeline.
- Wallet, whale, or token analysis.
- Trading, prediction, or live execution.
- AI or domain-agent implementation.

Solana remains the target chain for a later domain phase. Helius has not been selected as the final provider.

## Engineering principles

- Build small and scale later; do not introduce microservices only to appear scalable.
- Prefer clear module boundaries and contracts over a larger number of services.
- Keep the foundation maintainable and proportionate to the current team, budget, and development hardware.
- Preserve provenance, timestamps, auditability, and replayability as design goals for future data flows.
- Distinguish planned, documented, and implemented work explicitly.

## Accepted architecture decisions

These decisions establish direction; they are not claims of implementation.

- **Monorepo and modular monolith:** the modular monolith is the initial architecture direction. See [ADR 0001](../adr/0001-modular-monolith.md).
- **Evolution direction:** Modular Monolith → Event-Driven Architecture → Microservice Evolution. This is a conditional direction, not a schedule or an automatic migration.
- **PostgreSQL:** planned as the platform's single source of truth. See [ADR 0002](../adr/0002-postgresql-source-of-truth.md).
- **Event-first design:** accepted as a design direction for auditability and replayability. It does not select full event sourcing or delivery guarantees. See [ADR 0003](../adr/0003-event-first-design.md).

## Current repository structure and boundary evidence

The current worktree contains the project directories shown in [README.md](../../README.md), including `apps/api/`, `services/`, `packages/`, `migrations/`, `docs/adr/`, `docs/engineering/`, `infra/docker/`, and `tests/`. The `smart_money_ai/` package contains runtime configuration, an application factory, and an ASGI entrypoint; `tests/` contains focused configuration and application tests. `docs/` contains the three ADRs and two engineering documents. `apps/api/`, `services/`, `packages/`, `migrations/`, and `infra/docker/` remain without project files.

The repository-level package and entrypoint now provide a small application boundary, alongside the accepted modular-monolith direction. The detailed domain module contracts, ownership rules, dependencies, and deployment boundaries remain undecided. Directory names alone do not establish them.

| Observed path | What current evidence supports | What it does not establish |
| --- | --- | --- |
| `apps/api/` | An empty directory whose name is consistent with the conceptual API Service in the planned MVP topology. | An implemented API, internal contract, module ownership, dependencies, or independent deployment. |
| `services/` | An empty directory exists. | A worker implementation or a mapping of the conceptual Worker Service to this directory. |
| `packages/` | An empty directory exists. | Shared-package responsibilities or dependency rules. |
| `migrations/` | An empty directory exists; explicit, versioned migrations are a design requirement. | A schema, migration tool, or migration implementation. |
| `infra/docker/` | An empty directory exists; Docker Engine/Compose are planned technologies. | A Dockerfile, Compose configuration, or running stack. |
| `smart_money_ai/` | Runtime configuration, a FastAPI application factory, and an ASGI `app` entrypoint exist. | Domain module boundaries, external service wiring, or deployment configuration. |
| `tests/` | Focused `unittest` tests cover configuration and application initialization/health. | A broader application test suite or configured project test command. |
| `docs/adr/`, `docs/engineering/` | These contain the three ADRs and this baseline. | Application or operational behavior. |

The Section 17.4 repository list is a historical snapshot, not a substitute for this current worktree inventory. The planned API Service, PostgreSQL, NATS JetStream, and Worker Service are conceptual MVP components; they do not have to be separate deployments unless a future requirement justifies that choice.

## Module Boundary Design Guidance

This section records architecture guidance and open questions; it does not define the concrete domain modules, packages, or deployments.

### Accepted

- **Modular Monolith** remains the initial architecture, as recorded in [ADR 0001](../adr/0001-modular-monolith.md).
- PostgreSQL as the planned source of truth and event-first design as a direction are recorded in [ADR 0002](../adr/0002-postgresql-source-of-truth.md) and [ADR 0003](../adr/0003-event-first-design.md). These decisions do not establish module or deployment boundaries.

### Proposed

- Separate logical responsibilities before introducing package or deployment boundaries.
- Treat `apps/api/` as a candidate inbound entrypoint; its presence does not mean an API module is implemented.
- If background work is needed, treat Worker as an additional entrypoint from the same codebase. This guidance does not decide whether it runs in the same process.
- Keep persistence adapters from taking over application semantics or all data ownership.
- Keep projections with the relevant reader/feature until a concrete need justifies a separate logical boundary.
- Create a shared package only when a stable shared contract and real reuse need exist.
- Keep `services/`, `packages/`, `migrations/`, and `infra/docker/` as scaffolding; their names do not assign implementation responsibilities or deployment boundaries.

These proposals require validation against concrete requirements before being treated as accepted architecture decisions.

### Open

- Events and Audit have different conceptual purposes; whether they should be separate logical modules is undecided.
- No decision has been made to split Worker into a separate deployment or service.
- Exact module responsibilities, contracts, ownership, dependencies, and any future package boundaries remain undecided.

## Planned technology stack

The planned stack is Python, FastAPI, PostgreSQL, NATS JetStream, Docker Engine and Docker Compose, Make, and Git. **uv is accepted** as the Python environment and dependency management tool. The root `pyproject.toml` defines the project metadata and Python compatibility range `>=3.12,<3.15`; the application uses FastAPI, and runtime configuration uses `python-dotenv` to read the local `.env` file. `uv.lock` records these dependencies. No database, broker, worker, or infrastructure component is thereby established. Metadata validation does not establish that the full Python range has been verified. The planned infrastructure technologies are not evidence of installed or running project components.

## Storage and event design concepts

PostgreSQL is planned as the single source of truth. The following schema layout has been discussed as a design concept, not implemented database structure or finalized DDL:

- `public`: no application tables.
- `platform`: service metadata and operational data.
- `events`: planned storage area for event records and snapshots; this does not select full event sourcing or finalize an event-store model.
- `audit`: audit/investigation records and access logs.
- `projections`: read models.

Event records and snapshots are part of the planned storage architecture, while PostgreSQL remains the planned platform source of truth. Event-first is a design principle; full event sourcing has not been decided or implemented. Replay semantics, delivery guarantees, outbox, and dead-letter strategy remain open or deferred as described in ADR 0003. Explicit and versioned migrations, provenance, timestamps, auditability, and replayability are design principles. No migrations, schema, database, event broker, or event processing are implemented.

## Secure development configuration

Use `.env.example` as a non-secret template and keep real credentials in a local `.env` file excluded from version control. `smart_money_ai.config.load_settings()` loads the supported application settings from `.env` and process environment variables, with process environment values taking precedence. No secret-management service is established by this documentation.

## Local validation and engineering workflow

### Available in the current repository/workspace

Git and Python are available in the current review shell. The following checks do not require the planned application stack:

- `git status --short --branch --untracked-files=all` — inspect tracked changes and untracked files.
- `git diff --check` — check whitespace in tracked diffs. It does not inspect untracked file contents.
- `git check-ignore -q .env` — verify that `.env` is ignored (expected exit status `0`).
- `git check-ignore -q .env.example` — verify that `.env.example` is not ignored (expected exit status `1`).
- Use Python's standard library to check text files, including untracked documentation, for trailing whitespace and a final newline:

  ```sh
  python - <<'PY'
  from pathlib import Path

  files = [Path("README.md"), Path("docs/engineering/session-1-baseline.md")]
  for path in files:
      content = path.read_bytes()
      trailing = sum(
          1 for line in content.splitlines()
          if line.endswith((b" ", b"\t"))
      )
      print(
          f"{path}: exists={path.is_file()}, "
          f"trailing_whitespace={trailing}, "
          f"final_newline={content.endswith(bytes([10]))}"
      )
  PY
  ```

These commands validate repository state and documentation/configuration hygiene; they do not validate application behavior.

### Not yet available as project validation

- **Tests:** focused standard-library `unittest` tests cover runtime configuration and application wiring/health; `make test` runs them. There is no broader test suite.
- **Lint and type checking:** no project configuration is present; `ruff` and `mypy` are unavailable in the current review shell.
- **API/worker checks:** a minimal `GET /health` endpoint exists and has focused tests; no worker implementation or broader API test suite exists.
- **Database/migrations:** no schema, migration files, database configuration, or migration validation is present.
- **Docker Compose:** `infra/docker/` is empty; no project Compose configuration or service health checks are available. The presence of a Docker executable alone does not provide a project stack.
- **Make targets:** `sync`, `run`, `test`, `lock-check`, and `check` are available in the root Makefile. `run` serves the ASGI application on `127.0.0.1:8000`.

Add those validations only when their corresponding project configuration and implementation exist. Do not treat planned tools as current validation commands.

## Undecided details

- Exact module boundaries, contracts, ownership, dependencies, and future service boundaries.
- Whether and how the discussed schema layout becomes finalized DDL; schema details, indexing, partitioning, retention, and database topology.
- Event format, delivery semantics, retention, and replay compatibility; full event sourcing remains undecided.
- Outbox and dead-letter strategies.
- Which dependencies are justified by concrete implementation needs.
- Blockchain provider selection; Helius is not selected.
- Whether or when architecture should evolve beyond the modular monolith.

## Constraints and risks

- One developer currently; a possible team of 2–5 developers later.
- Approximate budget of Rp500,000 per month.
- Development hardware: AMD A9 dual-core CPU, 12 GB RAM, 500 GB SSD, Arch Linux.
- Avoid premature microservices and infrastructure that exceeds the project’s current needs.

Risks include operational and budget overhead from premature infrastructure; mistaking directory names or conceptual topology for implemented module contracts; and treating discussed schema or event concepts as finalized decisions. Event semantics and data lifecycle choices should wait for concrete requirements.

## Foundation review criteria

Review the foundation for readiness when repository/module boundaries are documented to the level supported by evidence, secure configuration guidance is clear, accepted decisions and open questions are distinguished, storage/event design intent is recorded without guessed semantics, and current versus future validation steps are explicit. These are criteria for review, not a statement that Session 1 is complete or that all criteria have been met.
