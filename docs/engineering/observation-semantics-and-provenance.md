# Observation Semantics and Provenance

**Status:** M2 engineering specification; proposals in this document are not implementation decisions unless marked as confirmed M1 behavior.

## Purpose and boundary

This document describes the meaning and provenance of finalized Solana slot observations, records the behavior present in M1, and identifies decisions remaining after the M3 provider evaluation, M4 adapter specification, and M5 implementation. M3 is a provisional evaluation, not a final provider selection. M4 is a specification; M5 implements the adapter but does not establish live Solana connectivity.

M1 contains immutable, provider-neutral data models, a synchronous observation protocol, and a deterministic fake adapter. M5 adds a live HTTPS JSON-RPC adapter that validates responses and verifies genesis identity. The repository still has no polling process, persistence, freshness policy, or production source selection. The terms “source” and “observation” below describe the M1 contract unless a section explicitly labels a later implementation or future proposal.

## Confirmed M1 contract behavior

`FinalizedSlotObservation` represents a non-negative slot value reported with commitment `finalized`, associated with a `NetworkIdentity`, an `ObservationSource`, and an `observed_at` timestamp.

- `NetworkIdentity` contains non-empty `cluster` and `genesis_hash` strings. M1 does not establish that the hash belongs to the named cluster.
- `ObservationSource` contains a non-empty, provider-neutral `source_id`. The fake adapter defaults it to `fake`.
- Commitment is restricted to `finalized`.
- `observed_at` is assigned at the adapter boundary when the adapter receives the successful observation, not supplied by the source. It is a timezone-aware `datetime`, normalized to UTC, and represents local observation receipt time.
- `slot` is an integer greater than or equal to zero; booleans are rejected.
- `FinalizedSlotObserver.get_finalized_slot()` is synchronous. `ObservationError` is the domain error type in the interface.
- `FakeSolanaObservationAdapter` returns configured values and supports an injectable clock and deterministic failure. It performs no network access.

The base model does not impose ordering between observations, define a maximum age, compare a network identity to an expected network, or interpret source response metadata. It does not contain block time.

## Slot and time semantics

A Solana slot is an index in the slot schedule representing an opportunity for a leader to produce a block. Slots can be skipped, so not every slot necessarily contains a produced block. A slot is not a wall-clock timestamp and does not itself state when a block was produced. A slot observation at finalized commitment is a point-in-time report of a slot value from an observation source. It does not claim that every slot number corresponds to a produced block or that this contract contains the history of all blocks or transactions.

`observed_at` is assigned locally at the adapter boundary as receipt time for a successful observation; it is not a timestamp returned by the RPC source. It is distinct from a chain-provided block time, which is not part of M1 and must not be inferred from the slot number. If a future feature needs block time, it requires a separately defined field, source semantics, and validation rules.

The current model normalizes `observed_at` to UTC but does not verify clock synchronization, bound clock skew, record request start time, or calculate staleness. Freshness is therefore not an intrinsic property of an M1 observation.

## Identity and minimum provenance

The fields carried by M1 provide the minimum provenance available in the current contract:

| Field | Provenance meaning in M1 |
| --- | --- |
| `network.cluster` | Human-readable cluster label supplied by the caller. |
| `network.genesis_hash` | Network identity value supplied by the caller; the model checks only that it is non-empty. |
| `commitment` | The observation is labeled `finalized`. |
| `slot` | The reported non-negative slot value. |
| `source.source_id` | Provider-neutral identity assigned to the observation source. |
| `observed_at` | UTC-normalized local receipt time assigned by the adapter, not source-supplied time. |

These fields do not prove that a source response is authentic, that a source is on the named network, or that two sources agree. The M1 fake can exercise the contract but provides no external evidence.

### Additional provenance that may be needed later

The following are possible future metadata, not accepted M1 fields or requirements. Their need and semantics should be established from the use case before implementation:

- Request start and completion times, to distinguish end-to-end latency from receipt time.
- A source response context such as a source-reported slot, commitment, or response identifier, if the selected interface exposes meaningful values.
- Adapter/software version and a more specific source instance identity, to reproduce or compare observations across deployments.
- A request or correlation identifier for linking logs without exposing credentials.
- A source-reported chain time, only if separately needed and clearly distinguished from `observed_at`.
- Clock quality or synchronization information if freshness or cross-source time comparisons require it.
- Validation outcome or a structured reason for rejecting a source response, if consumers need auditable quality decisions.

Do not add these fields merely for completeness. Decide their meaning, ownership, retention, and privacy implications when a concrete requirement exists.

## Data quality cases and interpretation

The table distinguishes the current base-contract behavior from possible future evaluation. The future column is guidance for design discussion, not a policy implemented by M1.

| Case | Interpretation | M1 behavior | Future consideration (proposed) |
| --- | --- | --- | --- |
| Duplicate slot observations | Separate calls or sources may report the same finalized slot. This can be a normal repeated sample; it is not necessarily duplicate event delivery. | Each valid call can produce an observation. No uniqueness or deduplication rule exists. | If observations are stored later, define whether identity includes source and observation time. Do not discard samples without a use-case-specific rule. |
| Increasing slots | A later-observed slot may be greater than an earlier one, consistent with forward progress. | Both values are valid; no progression check exists. | A monitor may compare observations in a defined sequence, accounting for source, network, and completion order. |
| Slot gaps | Two observations may have non-consecutive slot values. Skipped slots can occur, and a gap in samples can also reflect sampling cadence. A numeric gap alone does not prove missing data or chain failure. | Both values are independently valid; gap size is not checked. | Interpret a gap only against an agreed sampling expectation and source semantics. Do not infer missing blocks or transactions from the gap alone. |
| Slot regression or out-of-order responses | A lower slot may arrive after a higher slot because requests completed out of order, sources differ, or a source reports a lagging view. | The base model permits any non-negative slot and does not compare observations. | A higher-level consumer may flag or contextualize a regression using request order, source identity, network, and timestamps. Do not reject it in the base model. |
| Stale observation | An observation may be old relative to when a consumer uses it. M1 has no freshness threshold. | `observed_at` is recorded and normalized; no age calculation or stale flag exists. | Define a freshness objective, reference clock, and behavior for stale data before a consumer relies on it. Receipt time alone does not establish when the source state was current. |
| Genesis hash mismatch | A source may be connected to a network other than the expected network, or configured identity may be wrong. | `NetworkIdentity` checks non-empty strings only; it does not compare a source response with an expected identity. | Establish how expected cluster/genesis identity is configured and verified, and whether a mismatch is fatal or quarantined. |
| Timeout or source unavailability | The source may fail to respond or be unavailable. | The interface defines `ObservationError`; the fake can raise it deterministically. No live timeout, retry, or availability behavior exists. | Set operational timeout and error-classification requirements before live adapter implementation. Retry and recovery policy remain separate decisions. |
| Invalid source response | A live source may return missing, malformed, inconsistent, or unsupported values. | There is no live response parser. Domain model construction rejects invalid types, negative slots, non-finalized commitment, invalid network/source types, and naive timestamps. It does not validate provider payloads or network/hash consistency. | Define response validation and error reporting against a chosen source contract; preserve enough context to diagnose invalid data without leaking secrets. |

### Why duplicates and gaps are not automatically errors

The contract describes a sampled value, not a unique event stream. Repeated observations of the same slot are expected when reading a current value more than once. Likewise, observed slot values need not be consecutive: slots can be skipped, and an observer may sample less frequently than the chain advances. Without a specified cadence and completeness guarantee, duplicates and gaps are observations to interpret, not automatic validation failures.

### Why base-model validation must allow regression

The base model represents one observation independently. It has no ordering key, request-start time, source comparison rule, or stateful prior observation. Concurrent requests can complete in a different order from submission, so a lower slot can be returned after a higher slot even when each result is valid for its own request. Rejecting regression in the value model would conflate observation validity with a consumer's temporal or source-consistency policy. Any such policy belongs in a later component with explicit ordering and comparison semantics.

## Remaining decisions after M3, M4, and M5

The M3 document compares candidate providers and gives a provisional recommendation. The M4 document specifies the adapter, and M5 implements that provider-neutral contract. The following operational decisions remain; none represents live endpoint verification:

1. **Final provider selection:** M3 provisionally prefers Chainstack Developer Free and names QuickNode as the comparison/fallback candidate. No provider is selected finally; the comparison and account-level limits remain to be confirmed.
2. **Live endpoint smoke test:** no real endpoint has been tested. Verify network identity, finalized response shape, endpoint behavior, and latency from the intended deployment region before adopting a provider.
3. **Operational objectives:** define acceptable observation cadence, timeout budget and total-call deadline, freshness target, clock skew, and any availability objective. M1 defines no such objectives; M5 implements a finite timeout per request, not a production-tested operational choice.
4. **Live endpoint verification:** test the actual endpoint's response shape, identity, and behavior from the intended deployment region. The M5 adapter has deterministic unit-test coverage but has not been tested against a live endpoint.
5. **Network identity expectation:** establish the supported cluster labels and authoritative genesis hashes, then verify those values against the selected endpoint. The M1 model itself does not verify the cluster/hash relationship.
6. **Credential handling and safe diagnostics:** decide how endpoint credentials are stored and rotated and which authentication form is used. M5 suppresses endpoints, credentials, bodies, and low-level exception text from errors and does not log request details; this behavior has not been validated against a provider endpoint.
7. **Freshness, ordering, and source semantics:** decide how consumers interpret stale observations, regressions, source disagreement, and response context. M1 has no ordering or freshness policy; M4 only specifies one request's response validation.
8. **Invalid response handling:** define any additional source-specific response validation and diagnostic requirements without changing the confirmed M1 model unless separately approved.
9. **Evidence lifecycle:** if persistence is proposed later, define retention, deduplication, replay, and audit needs in that storage design. M1 adds no persistence.

These remaining decisions do not undo the completed M3 comparison, M4 specification, or M5 adapter implementation. Provider selection remains provisional and no live smoke test has occurred. M5 implements only synchronous read-only HTTPS JSON-RPC calls; it does not implement WebSocket, gRPC, streaming, polling, persistence, scheduling, or ingestion.
