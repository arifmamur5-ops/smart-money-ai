# Smart Money AI Capability and Ownership Boundaries

**Purpose:** Define what Smart Money AI owns, what Swarm Forge owns, and what remains future work. This is a scope and evidence document, not an implementation plan for generic infrastructure.

## Status meanings

- **Existing** — supported by current repository evidence or explicitly identified as an existing capability of its owning project. It does not imply production readiness.
- **Documented/Planned** — a design direction or intended capability is recorded, but implementation is not evidenced.
- **Missing** — needed by Smart Money AI to operate as an application, with no implementation evidenced in this repository.
- **Deferred** — intentionally gated to a later phase; not current implementation scope.
- **Unverified** — evidence is insufficient to claim that a capability is implemented or available.

Directories, ADRs, and technology choices do not establish running components. The initial foundation baseline had eight files. Subsequent work has added runtime configuration and a small ASGI application; no database, broker, worker, or domain implementation is evidenced.

## 1. Generic workflow infrastructure — Swarm Forge

Swarm Forge owns generic workflow infrastructure. The following are identified as existing or previously implemented there; this document does not verify their present code state or production readiness:

| Capability | Status | Boundary |
| --- | --- | --- |
| Task contracts and lifecycle/state machine | Existing (Swarm Forge-owned) | Generic task identity, states, and transitions belong there. |
| Workflow orchestration and task execution primitives | Existing (Swarm Forge-owned) | Generic workflow and execution coordination belong there. |
| Policy gate | Existing (Swarm Forge-owned) | Generic policy enforcement infrastructure belongs there. |
| Audit integrity mechanism | Existing (Swarm Forge-owned) | Generic lifecycle/integrity audit belongs there. |
| Task persistence, attempts, retry, and recovery primitives | Existing (Swarm Forge-owned) | Generic task state and recovery mechanics belong there. |
| Outbox persistence primitive | Existing (Swarm Forge-owned) | This is persistence only; it is not a complete delivery or dispatch system. |

These capabilities do not make Swarm Forge a complete multi-agent LLM platform. End-to-end agent/tool execution is incomplete; NATS integration is absent; and exactly-once delivery or production readiness must not be assumed.

Smart Money AI must not implement another task engine, task lifecycle/state machine, workflow orchestrator, agent orchestration framework, policy gate, generic audit framework, attempt/retry/recovery engine, outbox, or generic execution framework.

## 2. Smart Money AI application capabilities

Smart Money AI owns the application entrypoints, contracts, and domain behavior. These are application needs, not reasons to duplicate Swarm Forge infrastructure.

| Capability | Status | Evidence or scope |
| --- | --- | --- |
| Application entrypoint and wiring | Existing | `smart_money_ai.main:app` is the ASGI entrypoint; `smart_money_ai.app.create_app()` wires settings and the optional finalized-slot observer into the app. |
| Runtime configuration loading | Existing | `smart_money_ai.config.load_settings()` loads application settings and optional Solana RPC values from `.env` and process environment variables. Invalid or absent RPC configuration does not prevent app startup. |
| Application/domain module boundaries | Documented/Planned | Modular monolith is the accepted initial direction; concrete module contracts and dependency rules remain undefined. |
| Smart Money AI API contracts and domain request/response models | Existing (limited) | `GET /solana/observations/finalized-slot` exposes the documented finalized observation response; broader API contracts remain future work. |
| Domain/application error handling | Existing (limited) | The observation route maps unavailable/invalid RPC configuration, adapter failures, and unexpected errors to sanitized HTTP responses. |
| Process health endpoint | Existing | `GET /health` confirms the process can respond; it does not assert infrastructure readiness. |
| Dependency readiness checks | Deferred | Add only when the application depends on concrete infrastructure whose readiness must be evaluated. |
| Focused application tests | Existing | Standard-library `unittest` covers settings, factory wiring, health, and deterministic finalized-slot API behavior; no live RPC test is included. |

“Generic platform foundation” is too broad to be an implementation task. Replace it with scoped work items such as “load and validate runtime configuration,” “define the first application entrypoint and its wiring,” or “specify the health/readiness contract.” Each item should name its behavior, boundary, and acceptance evidence before implementation.

## 3. Smart Money AI domain capabilities — future gates

These are Smart Money AI domain responsibilities, but are deferred. They are not part of this documentation task and must not be inferred from the repository foundation.

| Capability | Status | Gate before implementation |
| --- | --- | --- |
| Finalized Solana slot observation contract | Existing | The provider-neutral observation contract, fake adapter, and synchronous HTTPS JSON-RPC adapter are implemented. The API invokes the adapter only on request. |
| Blockchain observation and live source adapters | Existing (limited) | Only finalized-slot reads are implemented. No provider is selected or live endpoint verified; Helius is not selected. Broader source needs remain deferred. |
| On-chain observations and domain history | Deferred | Define observation identity, timestamps, provenance, retention, and replay needs. |
| Smart wallet dataset domain foundation | Existing (offline only) | Versioned researcher-curated membership, provenance, optional normalized activity facts, and deterministic snapshots exist in `smart_money_ai.wallet_dataset`; no wallet source, ingestion, persistence, scoring, or classification is implemented. |
| Wallet intelligence and profiling | Deferred | Establish research methodology and evidence standards before adding profiling, scoring, classification, or other analysis. |
| Wallet behavioral profiling and whale forensics | Deferred | Define research questions, methodology, and evidence standards. |
| Token/protocol intelligence | Deferred | Define target coverage and the source/evidence model. |
| Research, replay, and backtesting | Deferred | Define reproducibility and the historical data needed to support it. |
| Paper trading, risk management, and execution sandbox | Deferred | Define simulation boundaries, risk controls, and validation gates. |
| Live execution | Deferred | Requires explicit strict readiness gates, including validated data, controls, monitoring, and operational readiness. |

The finalized slot observation represents a slot reported at finalized commitment; a slot is not block time. `observed_at` records when the adapter obtains the observation, not when a block was produced. The source identity is provider-neutral. Deterministic fake and mocked-transport tests exercise the contract without network access or provider selection. The API requests a live read only when explicitly called. Persistence, ingestion, transaction or wallet data, and analysis remain out of scope.

## 4. Infrastructure and data-platform decisions

| Decision/capability | Status | Current boundary |
| --- | --- | --- |
| Modular monolith as initial architecture | Documented/Planned | Accepted direction in ADR 0001; an application package and ASGI app exist, while concrete domain module boundaries remain undefined. |
| PostgreSQL as platform source of truth | Documented/Planned | Accepted direction in ADR 0002; no database, schema, migrations, or running service is evidenced. |
| Event-first design | Documented/Planned | Accepted direction in ADR 0003; not a selection of full event sourcing or delivery guarantees. |
| NATS JetStream | Documented/Planned | Part of the planned technology direction only; no broker or integration is evidenced. |
| Worker process/deployment | Unverified | A conceptual component only; no worker implementation or deployment topology is evidenced. |
| Docker Engine/Compose application stack | Documented/Planned | Planned technology; no project Dockerfile, Compose stack, or running application stack is evidenced. |
| Schema, event format, retention, replay semantics, delivery guarantees, outbox/dead-letter strategy | Unverified | Unresolved design details; decide only when concrete requirements need them. |

The platform storage direction does not assign every record to a generic platform event store. Smart Money AI may own domain persistence and domain events for on-chain observations, wallet/token records, provenance, research findings, and analytical history when their domain semantics require them.

Those records must not recreate Swarm Forge task/workflow lifecycle state, its task event store, generic lifecycle audit, or its outbox. Keep domain evidence/history distinct from generic orchestration state. Do not add a broker, database, worker, or container stack merely to complete a vague “foundation” task.

## 5. Swarm Forge integration boundary

Swarm Forge and Smart Money AI are separate projects and repositories. Swarm Forge ownership does **not** mean Smart Money AI is integrated with it. No dependency, API connection, shared runtime, or data flow between them is established by the current evidence. Do not create an integration or dependency as part of this boundary review.

If a concrete future requirement calls for integration, first define the application use case, contract, failure behavior, and operational need as a separate decision. Reuse of generic workflow capabilities would not transfer domain ownership to Swarm Forge or make Smart Money AI responsible for rebuilding those capabilities.

## 6. Genuine Smart Money AI capability gaps

The current application gaps are concrete module contracts, broader API models/contracts beyond finalized-slot observation, dependency readiness checks when infrastructure is introduced, and a broader application test harness as the application grows. These remain unimplemented or deferred; the minimal entrypoint, process health endpoint, finalized-slot endpoint, and focused tests do not imply additional application behavior.

The absence of a Smart Money AI task engine, orchestrator, policy gate, generic audit system, retry engine, outbox, or generic execution framework is **not** a Smart Money AI gap. Those responsibilities belong to Swarm Forge. Domain-specific observation provenance, research evidence, and analytical history remain valid Smart Money AI needs when a gated domain capability establishes their requirements.
