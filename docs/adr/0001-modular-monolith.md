# ADR 0001: Modular Monolith as the Initial Architecture

**Status:** Accepted
**Date:** 2026-11-17

## Context

Smart Money AI is in Session 1, establishing a generic platform foundation. The project is currently being developed by one developer, may later involve 2–5 developers, and has an approximate monthly budget of Rp500,000. Development hardware is an AMD A9 dual-core system with 12 GB RAM and a 500 GB SSD running Arch Linux. The project principle is to build small and scale later, avoiding premature microservices and heavy infrastructure.

The accepted architectural direction is a monorepo and a planned evolution from Modular Monolith to Event-Driven Architecture and then Microservice Evolution. The evolution path is directional; it does not establish that any stage has been implemented or define a migration schedule.

## Decision

Use a **modular monolith as the initial architecture direction**, within a monorepo. Keep the platform organized around modular boundaries while the foundation is developed. Treat any later move toward event-driven architecture or microservices as a separate decision based on demonstrated needs.

This is an accepted design decision, not a claim that a modular monolith or application code already exists.

## Consequences

- Initial architecture work can focus on clear module boundaries without requiring independently deployed services.
- The repository can evolve from one codebase while the project and team are small.
- Future extraction or broader event-driven design would require explicit design and migration work; it is not automatic.
- Module inventory, specific boundaries, and deployment details remain to be defined when implementation requirements are known.

## Tradeoffs

- A single initial architecture limits operational overhead but requires care to keep module boundaries understandable as the codebase grows.
- Deferring service separation avoids premature infrastructure, but later evolution may require refactoring and migration effort.
- The directional evolution path gives a broad trajectory without resolving when the costs of a new stage are justified.

## Reevaluation triggers

Reevaluate this decision if concrete requirements show that modular boundaries cannot meet independent scaling, deployment, ownership, or reliability needs; if team size or coordination needs change materially; or if measured workload and operational constraints justify additional infrastructure. Reevaluate before introducing microservices rather than treating the stated evolution path as an automatic sequence.
