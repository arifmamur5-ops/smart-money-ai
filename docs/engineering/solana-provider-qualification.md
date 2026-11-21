# Solana Provider Qualification Framework

**Status:** Evaluation framework only. No provider has been selected or qualified, and no live provider smoke test has been performed. Helius is not preselected.

## Purpose and boundaries

Evaluate each provider separately for (A) basic Solana RPC observation and (B) historical wallet data acquisition. Passing the basic RPC gates does **not** qualify a provider to supply historical wallet data. This document defines evidence to collect; it does not select a provider, set a score threshold, configure an endpoint, or authorize a live test.

For every evaluation, record the provider and plan, the documentation or account terms reviewed and their review date, test conditions, sanitized results, unknowns, and limitations. Prefer provider documentation and reproducible tests over marketing statements. If evidence is missing, record the capability as unknown rather than assuming it works.

## A. Basic Solana RPC observation

### Mandatory acceptance gates

All gates below must pass before a provider can be called qualified for the current finalized-slot observation:

| Gate | Required evidence and pass condition |
| --- | --- |
| Network identity | An expected genesis hash is independently verified for the intended cluster. `getGenesisHash` returns that exact hash. Record the configured cluster label separately; the label is not derived from the hash. |
| Finalized slot | `getSlot` succeeds with explicit `finalized` commitment and returns a valid non-negative integer slot. |
| JSON-RPC behavior | Request/response envelope, response ID, result shape, and relevant HTTP and JSON-RPC error behavior are validated against provider documentation and a smoke test. |
| Authentication and security | Authentication requirements are documented. HTTPS and credential handling are understood; secret-bearing URLs or keys are not printed, logged, or committed. |
| Rate limits and operational constraints | Applicable plan quotas, rate limits, throttling behavior, and relevant method restrictions are documented. Unknown limits remain an open gate. |
| Recorded smoke evidence | A sanitized smoke-test result records the provider, endpoint type, timestamp, network, results, and limitations. Credentials and the secret URL are excluded. |
| Limitations | Observed and documented limitations are explicitly recorded. One successful call is not presented as an SLA or reliability guarantee. |

Failure of any gate means the provider is not qualified for basic observation. A credential-bearing endpoint must remain in local secret configuration and must not be copied into reports.

### Comparative evaluation after gates pass

Compare qualified candidates on:

- Repeatability and observed availability over a suitably bounded, low-rate observation period.
- Published reliability evidence and operational status communication.
- Rate headroom for the project's actual low-frequency use.
- Price, included quotas, overage, trial duration, and the practical fit with the project budget.
- Documentation clarity and completeness for methods, response errors, authentication, quotas, and plan limits.
- Developer ergonomics, such as endpoint setup, test access, and ease of reproducing the smoke check.

These are comparison factors, not substitutes for mandatory gates. Do not turn this framework into a numerical score or threshold without a separate decision.

## B. Historical wallet data acquisition

Historical acquisition is a separate capability and requires its own evidence and acceptance decision. Basic `getGenesisHash` and finalized `getSlot` success does not show that an RPC or indexing provider can enumerate complete address history.

The dimensions below are mandatory gates for claiming qualification for a defined historical scope. A provider with an unknown or failing dimension is not qualified to claim complete coverage for that scope. A deliberately bounded or partial future acquisition may proceed only after its narrower scope, detectable gaps, and limitations are explicitly reviewed and recorded; that does not qualify the provider for complete history. Among candidates that pass the applicable gates, compare practical throughput, cost fit, documentation quality, security controls, and developer ergonomics for the specific plan.

| Evaluation dimension | Evidence to obtain | Minimum evidence before relying on the capability |
| --- | --- | --- |
| Address-history coverage | Documented address query scope and bounded queries for representative addresses and time/slot ranges. | Required history range and supported transaction classes are explicit; unavailable ranges are recorded. |
| Pagination and query bounds | Cursor/offset semantics, page limits, boundary behavior, termination behavior, and repeat queries across page boundaries. | Pagination is deterministic enough to detect duplicates, skipped pages, and incomplete termination; query limits are documented. |
| Retention and archive availability | Plan-specific retention/archive policy and representative queries for older history. | Required age range is available or explicitly excluded; marketing terms alone are insufficient evidence. |
| Completeness and ordering | Ordering guarantees, stable boundaries, duplicate behavior, and controlled overlapping queries. | The ordering and omission behavior are documented and omissions can be identified or bounded. |
| Transaction metadata quality | Representative transaction responses including account keys, signer/fee-payer metadata, instructions/program IDs, and relevant metadata fields. | The data supports only the explicit relationship assertions required by the dataset; arbitrary account presence is not treated as signer or invocation evidence. |
| Slot and commitment semantics | Documentation of returned slots and finality/commitment behavior for historical results. | Slot and commitment semantics are known for every imported fact; ambiguity blocks finalized-history claims. |
| Failed transactions and transaction versions | Documentation and fixtures for failed transactions and supported transaction versions. | Inclusion, omission, and unsupported-version behavior are known and reflected in the query policy. |
| Gaps, pruning, and omissions | Pruning policy, known gaps, errors for unavailable history, and tests at range boundaries. | Material gaps are disclosed and handled conservatively; unknown omission behavior cannot support completeness claims. |
| Reproducibility | Query parameters, API/version changes, bounded result references, and retention of source artifacts or stable references. | A source run can record its exact bounds, source identity, acquisition time, and evidence references. |
| Rate limits and throughput | Plan-specific quotas and measured throughput for a bounded representative query. | A proposed bounded acquisition fits documented limits without relying on unapproved infrastructure. |
| Cost and usage limits | Historical/indexing charges, quota consumption, overage, retention tiers, and export costs. | A bounded acquisition estimate and cost ceiling are understood before use. |
| Documentation and security | Dated source docs, authentication scope, TLS, credential rotation/revocation, and safe handling review. | Material limits and unknowns are recorded; credentials can be restricted and kept out of source control, logs, and provenance text. |

Unknown coverage, pagination, retention, or omission semantics must not be represented as proven completeness. A later, explicitly bounded partial acquisition may be considered only with its limits, query bounds, source runs, and evidence retained, and with coverage labels no stronger than that evidence supports. No historical collection is implemented or approved by this framework.

## Future M6 smoke-test checklist

This is an operator-executed procedure for a future explicitly approved provider. **Do not run it until a provider and endpoint have been approved.** Use the canonical application configuration names: `SOLANA_RPC_ENDPOINT`, `SOLANA_CLUSTER`, `SOLANA_GENESIS_HASH`, `SOLANA_RPC_TIMEOUT_SECONDS`, and optional `SOLANA_RPC_SOURCE_ID`.

1. Authenticate using the provider's documented method without exposing credentials in shell history, terminal output, logs, or reports.
2. Call `getGenesisHash`.
3. Compare the returned hash with an independently verified expected hash for the intended cluster.
4. Call `getSlot` with `{"commitment":"finalized"}`.
5. Validate the JSON-RPC version, request ID, result shape, and non-negative integer slot.
6. Repeat at a low rate to observe basic stability and rate-limit behavior. Do not treat this as a reliability study.
7. Record provider identity, endpoint type (never the secret URL), test timestamp, network, sanitized results, and observed limitations.
8. Never print, log, or commit API keys or credential-bearing URLs.

No provider has been selected, no live provider smoke test has been performed, and Helius is not preselected. One successful smoke test is not an SLA, a reliability guarantee, or proof of historical completeness.
