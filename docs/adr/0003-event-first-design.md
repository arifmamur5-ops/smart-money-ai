# ADR 0003: Event-First Design Direction

**Status:** Accepted
**Date:** 2026-11-17

## Context

The platform accepts event-first design as a direction to support auditability and replayability. NATS JetStream is part of the planned technology direction, but no event broker is claimed to be installed or running. The project is in its generic platform foundation phase and should avoid premature infrastructure and unsupported implementation detail.

## Decision

Adopt **event-first design as an accepted design direction** for platform work, with auditability and replayability as its stated aims. Choose event handling and persistence details when concrete requirements are available.

This decision does not select full event sourcing and does not claim that event infrastructure or event processing has been implemented.

## Consequences

- Future designs should consider how relevant platform events can be audited and replayed.
- Concrete event contracts and operational behavior require follow-up decisions before implementation.
- The direction can inform design without requiring a broker or heavyweight event infrastructure during the foundation phase.

## Tradeoffs

- Considering auditability and replayability early can preserve future options.
- Event-first designs can add complexity; without defined event use cases and semantics, implementing infrastructure now risks premature abstraction and operational burden.
- Deferring details leaves requirements to be resolved before producers and consumers depend on event behavior.

## Reevaluation triggers

Reevaluate the scope or application of this direction if concrete platform requirements show that event-first handling does not provide proportionate auditability or replayability, or if its implementation cost conflicts with project constraints. Reassessment should be based on actual requirements and operational evidence.

## Explicitly undecided and not selected

- Full event sourcing has not been selected.
- Exactly-once delivery is not selected or promised.
- No event broker is claimed to be running.
- Event format, delivery semantics, retention, and replay compatibility remain undecided.
- Outbox and dead-letter strategies have not been selected or implemented.
