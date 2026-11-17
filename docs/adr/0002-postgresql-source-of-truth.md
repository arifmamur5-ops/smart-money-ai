# ADR 0002: PostgreSQL as the Planned Platform Source of Truth

**Status:** Accepted
**Date:** 2026-11-17

## Context

The accepted platform direction identifies PostgreSQL as the single source of truth for the main platform. PostgreSQL is part of the planned technology direction; this repository does not thereby claim that a database is installed, configured, or running.

The foundation also adopts event-first design as a direction for auditability and replayability. The relationship between event records and other persisted platform state has not been specified here.

## Decision

Treat **PostgreSQL as the planned single source of truth for the main platform**. This records the accepted role of PostgreSQL at the platform level. It does not define schema, data ownership boundaries, or persistence mechanisms.

This is an accepted design decision about planned responsibility, not an implementation claim.

## Consequences

- Future platform design should identify PostgreSQL as the authoritative source for platform state, subject to the scope of the concrete feature being designed.
- Persistence and any event-related storage must be designed consistently with this role when requirements are established.
- The decision does not prescribe schema or operational topology.

## Tradeoffs

- Naming one planned source of truth gives future platform work a clear consistency direction.
- The choice alone does not resolve data lifecycle, scaling, availability, or event replay needs; those require further decisions based on requirements.
- Deferring storage details avoids premature design but means implementation work must resolve them before they become necessary.

## Reevaluation triggers

Reevaluate if validated platform requirements show that PostgreSQL cannot reasonably serve the stated authoritative role within the project's operational constraints, or if the scope of authoritative platform state changes materially. Any alternative should be recorded with its rationale and migration implications.

## Explicitly undecided

This ADR does not decide schema, indexing, partitioning, retention, database topology, or the persistence relationship between event records and other state.
