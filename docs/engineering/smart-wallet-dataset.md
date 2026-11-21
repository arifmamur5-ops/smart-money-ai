# Smart Wallet Dataset — Offline Domain Contract

**Status:** Session 3 domain foundation implemented. No wallet source or provider has been selected.

## Scope and boundaries

This document specifies a finite, offline, researcher-curated cohort snapshot. The implemented package is `smart_money_ai.wallet_dataset`; it has no dependency on FastAPI, RPC transport, external services, or persistence. A candidate is a research designation only. The package does not collect live wallet data, classify accounts, score or rank addresses, infer identity or control, or make predictions or execution decisions.

Session 2 remains separate: its `GET /solana/observations/finalized-slot` endpoint reports the current finalized slot only. That observation does not provide transaction history or prove historical activity coverage. A finalized cutoff in this dataset is a fixed boundary for validating supplied facts, not a completeness claim.

## Terminology and identity

- **Address:** canonical base58-encoded Solana public key decoding to 32 bytes. This format does not establish account type, private-key control, ownership, human/entity identity, trader identity, or activity.
- **Wallet candidate:** an address with an explicit include or exclude decision in a reviewed research cohort. The term does not claim that the account is an externally controlled wallet.
- **Dataset definition:** stable dataset identifier plus semantic versions for definition, inclusion rule, and schema.
- **Dataset snapshot:** a finite definition and network-scoped set of membership decisions, source runs, evidence, optional normalized facts, coverage label, and finalized cutoff, with a deterministic digest.
- **Source run:** one specific seed-registration or acquisition operation. Its stable `run_id` is distinct from its reusable `source_id`.
- **Source evidence:** source-specific provenance retained independently from normalized activity facts.
- **Normalized activity fact:** a conservative relationship between one address and a transaction, optionally at an instruction location. It is not an ownership or trading assertion.

Every snapshot and related record carries the existing `NetworkIdentity`: the exact cluster label and genesis hash. Neither field is inferred from the other, and cluster labels are not rewritten or merged. Dataset membership is unique by `(cluster, genesis_hash, address)` within a snapshot; the snapshot digest identifies the resulting snapshot content.

## Implemented contracts

`smart_money_ai.wallet_dataset.models` provides immutable, slotted contracts:

- `DatasetDefinition(dataset_id, definition_version, inclusion_rule_version, schema_version)`. Versions use explicit `major.minor.patch` numeric syntax.
- `SourceRun(run_id, source_id, operation, acquired_at, network, coverage_status, window_start_slot, window_end_slot)`. Optional window bounds must be supplied together and ordered. Runs have no endpoint or credential fields.
- `SourceEvidence(evidence_id, source_run_id, evidence_type, reference, captured_at, network, activity_fact_id, researcher, rationale)`. Curated seed evidence requires researcher, source/reference, capture time, and rationale; it does not require a signature or activity fact. Other evidence types cannot carry curated researcher/rationale fields.
- `CandidateMembership(network, address, decision, reason_code, reason_version, provenance_refs, activity_fact_refs)`. Both include and exclude decisions are retained. Every membership has at least one evidence reference; a curated seed can have no activity references.
- `NormalizedActivityFact(network, signature, slot, address, relationship, instruction_location)`. Relationship meaning and minimum evidence are defined below. The fact never infers an initiator, owner, trader, or control from account-key presence.
- `CoverageStatus`: `complete`, `partial`, or `unknown`. These labels describe supplied metadata and are not guarantees about chain history.

`smart_money_ai.wallet_dataset.snapshot.build_snapshot()` is a pure offline constructor. It validates records, resolves source-run/evidence/fact references, checks exact network consistency and activity slots against the finalized cutoff, deduplicates exact duplicates, rejects conflicts, sorts records canonically, and returns a `DatasetSnapshot` with `SnapshotManifest`. Direct `DatasetSnapshot(...)` construction runs the same shared normalization and graph validation, then verifies manifest counts, run references, coverage bound, and digest. Mutable/non-tuple collections are rejected. Empty snapshots are allowed. `candidate_count` counts all retained membership decisions, including exclusions.

Activity fact semantic identity is `(cluster, genesis_hash, transaction signature, instruction location, address, relationship kind)`. Slot is content attached to that identity; conflicting slot/content for the same identity is rejected. Distinct relationship kinds and instruction locations remain distinct facts. Every normalized activity fact must have at least one `SourceEvidence.activity_fact_id` reference. Multiple evidence records and source runs can support the same fact and are retained separately.

### Activity relationship semantics

| Relationship | Required source assertion | Interpretation limits |
| --- | --- | --- |
| `SIGNER` | The address is explicitly marked as a signer in transaction message/account metadata. | Does not identify who controlled the signing key or why it signed. |
| `FEE_PAYER` | The address is explicitly identified as the transaction fee payer. | May also be a signer; represent both as separate facts when both assertions are supported. |
| `REFERENCED_ACCOUNT` | The address is referenced as an account by a transaction instruction. | Mere presence in an arbitrary transaction account list is insufficient. It does not prove ownership, control, or active behavior. |
| `PROGRAM_INVOLVEMENT` | The address is the program ID actually invoked by an instruction. | A program ID merely passed as an account to another program is insufficient. |

Multiple relationship facts may exist for one address and transaction; signer and fee-payer relationships can overlap. Populate `instruction_location` when the relationship is attributable to a particular instruction. Transaction-level signer and fee-payer relationships may have no instruction location. These are explicit caller-supplied evidence labels: this package validates their shape and references but does not parse transactions, independently verify the claim, or fetch chain data. No relationship implies wallet ownership, private-key control, identity, trader identity, or economic intent.

Evidence identity is `evidence_id`; exact repeated evidence is idempotent, while different content under the same ID is rejected. Source-run identity is `run_id`; exact repeats are idempotent, conflicting content is rejected. Candidate identity is the network-scoped address within a snapshot; exact repeats are idempotent, conflicting decisions/reasons/provenance are rejected. There is no last-write-wins behavior.

## Validation and unknown values

Addresses decode from canonical base58 to exactly 32 bytes; transaction signatures decode to exactly 64 bytes. Slots reject booleans and must be integers in `[0, 2**64 - 1]`. Activity slots above the snapshot's finalized cutoff are rejected. Timestamps must be timezone-aware and are normalized to UTC. Required identifiers and semantic versions are validated; source and evidence references must resolve, and related records must preserve the complete network identity.

Unknown data is not converted to zero, false, empty, or no activity. The contracts do not infer that a candidate has no activity merely because no facts were supplied. Address encoding does not distinguish program-derived addresses from key-controlled accounts, and no account-type classification is performed.

The domain accepts references and researcher-provided reason codes rather than raw acquisition payloads. Callers must supply non-secret references and must not place credentials, authorization headers, or endpoint secrets in provenance text. No secret-management or credential storage mechanism exists here.

## Timestamps, cutoff, and coverage

`SourceRun.acquired_at`, `SourceEvidence.captured_at`, and manifest `generated_at` are aware timestamps normalized to UTC. They describe local registration/acquisition/capture or snapshot-generation time, not Solana block time. No block-time field is present. The fixed `finalized_cutoff_slot` is labeled `finalized` and bounds any supplied activity facts. Session 2's current finalized-slot observation may inform a separately supplied cutoff, but it does not establish historical data coverage through that slot.

`SourceRun.window_start_slot` and `window_end_slot` describe the slot range associated with that source run's acquisition. When supplied, the bounds must be provided together and the start must not exceed the end. This acquisition window is independent of the snapshot's `finalized_cutoff_slot` and may extend beyond it; the cutoff does not truncate or redefine the run window. Activity facts with slots after the snapshot cutoff must not be included in the snapshot. A run's acquisition window alone does not establish that all activity in that range was successfully collected or that snapshot coverage is complete; coverage remains subject to the source run metadata and the coverage rules below.

Coverage status is an explicit caller-supplied label ordered `COMPLETE` (strongest), `PARTIAL`, then `UNKNOWN` (least informative). The snapshot may make a claim no stronger than its source-run statuses support: all runs `COMPLETE` support any snapshot status; `COMPLETE` plus `PARTIAL` supports only `PARTIAL` or `UNKNOWN`; any `UNKNOWN` run supports only `UNKNOWN`; and no source runs require `UNKNOWN`. A caller may choose a weaker status than the aggregate. The same rule is applied by `build_snapshot()` and direct `DatasetSnapshot(...)` construction.

This upper-bound rule only prevents a snapshot from overstating the labels attached to its listed runs. Coverage labels remain metadata claims, not independently verified guarantees of historical chain completeness. Source pagination, retention, pruning, query bounds, and omissions remain the source adapter's responsibility. No historical collector or completeness verifier is implemented.

## Canonical serialization and digest

`serialize_snapshot_content(snapshot)` returns the exact UTF-8 bytes hashed into `manifest.content_digest`. The representation is JSON with recursively sorted object keys, no insignificant whitespace, `ensure_ascii=False`, and non-finite numbers forbidden. Timestamps are UTC ISO 8601 with six fractional digits and `Z`. Optional values are serialized explicitly as JSON `null`; lists are retained as arrays.

Candidates, source runs, source evidence, and activity facts are sorted by their canonical serialized record bytes. Candidate reference arrays are sorted. The digest is lowercase SHA-256 hex over canonical JSON containing:

- Schema version and the complete dataset definition, including all three version fields.
- Exact network cluster and genesis hash.
- Finalized cutoff slot and `finalized` commitment.
- Coverage status and candidate-decision count.
- Canonically ordered candidate memberships, source runs, source evidence, and activity facts.

The digest excludes `generated_at`, `content_digest` itself, Python `repr()`, insertion order, and runtime object identity. Source-run acquisition timestamps and evidence capture timestamps are included because they are provenance content. Thus changing schema/definition/rule versions, network, cutoff, coverage, decisions, or evidence changes the digest; changing only snapshot generation time does not. The digest guarantees reproducible serialization of supplied inputs, not that the inputs are true, complete, or independently replayable. Exact source replay would require retaining the referenced source artifacts under a separately defined policy.

## Candidate workflow and source requirements

The supported initial workflow is to register researcher-supplied seeds with an explicit network, decision, versioned reason, source run, and curated evidence reference/rationale. Exclusions remain represented when present in the reviewed candidate pool. No transaction evidence is required for seeds and no social source is supported or implied.

Any future candidate/activity source should provide a stable source identity and per-acquisition run identity, explicit network identity including genesis hash, bounded and documented query/window semantics, pagination and coverage limitations, finalized semantics where applicable, stable references, acquisition/capture timestamps, and a way to surface omissions or source conflicts. Provider cost, access, retention, reliability, and exact capabilities must be evaluated before integration. No provider has been selected, and no provider capability is assumed here.

## Limitations and deferred decisions

- No live wallet data was collected; no provider was selected; no transaction history integration exists.
- No persistence, database schema, ingestion, RPC wallet query, polling, scheduler, or background synchronization was added.
- Session 2's M6 API exposes only current finalized slot observation.
- A finalized cutoff does not prove historical activity completeness.
- Researchers still need to define dataset-specific cohort rationale and reason-code vocabularies; this module validates their shape, not their scientific quality.
- Source references are opaque caller-supplied strings. Their retention, retrieval, authenticity, and privacy policies remain unresolved.
- Inclusion-rule review/approval, snapshot storage and publication, compatibility policy for future schema changes, exact artifact archival, and cross-researcher curation procedures remain open.
- Signature/address format validation establishes encoding and decoded length only; it does not prove chain inclusion, account type, or relationship correctness.

## Acceptance evidence and verification

The offline suite is `python -m unittest tests.test_wallet_dataset -v` (or the repository `make check`). It covers contract validation, curated seed provenance, activity identity and cutoff, reference/network integrity, direct snapshot validation, conservative coverage aggregation, duplicate/conflict behavior, canonical ordering, digest stability, and version/network/cutoff changes. Tests use fixed values and make no network calls.

This milestone does not alter M5–M6 API or observation contracts, and it does not claim live RPC verification, production readiness, provider reliability, historical completeness, or wallet intelligence.
