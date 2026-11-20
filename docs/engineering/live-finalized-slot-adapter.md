# Live Finalized Slot Adapter (M5)

**Status:** Implemented as a provider-neutral, read-only HTTPS JSON-RPC adapter. No provider has been selected and no live endpoint has been verified by this implementation.

## Purpose and boundary

`LiveFinalizedSlotAdapter` implements the existing synchronous `FinalizedSlotObserver` contract. It performs one `getGenesisHash` request and, if the exact configured hash matches, one `getSlot` request at `finalized` commitment. It returns the existing M1 `FinalizedSlotObservation`; it adds no provider-specific model fields and does not infer the configured cluster label from the hash.

Construction requires an HTTPS endpoint, a `NetworkIdentity`, a non-empty provider-neutral `source_id`, and a finite positive timeout in seconds. A clock callable may be supplied for deterministic use; the default is local aware UTC time. The adapter does not take credentials through a separate mechanism; endpoint URL authentication supported by an RPC service remains the caller's configuration responsibility.

Each request has its own timeout. The full operation uses two sequential requests, so wall-clock duration may approach twice the configured timeout plus local processing. The timestamp is captured after both successful responses and normalized to UTC by the existing M1 model.

## Validation and errors

The adapter validates HTTPS URL structure, HTTP success, UTF-8 JSON, the JSON-RPC 2.0 envelope and matching request ID, result presence, exact genesis hash identity, and an integer slot in `0..2**64-1` (with booleans rejected). Failures in transport, HTTP, redirects, response parsing, JSON-RPC, identity, slot validation, and clock output raise `ObservationError`. Configuration argument errors follow the existing model convention of `TypeError` or `ValueError` at construction.

The standard-library `urllib` transport verifies TLS certificates using its normal default context. Redirects are rejected before they can be followed, so credentials in the endpoint are not sent to a redirected destination. Error messages do not include the endpoint, credentials, response body, or underlying exception text; no request or response logging is performed. There are no retries.

## Validation commands

Run ordinary tests with `make test` (or `uv run --locked python -m unittest discover -s tests -v`). Tests inject the HTTP transport and do not access the public internet.

An optional live smoke check can be run manually after setting `SOLANA_RPC_ENDPOINT`, `SOLANA_CLUSTER`, and `SOLANA_GENESIS_HASH` in the local environment; `SOLANA_SOURCE_ID` defaults to `manual-smoke`, and `SOLANA_RPC_TIMEOUT` defaults to 10 seconds:

```sh
python -m scripts.solana_rpc_smoke
```

It invokes only `getGenesisHash` and finalized `getSlot`, prints safe observation fields on success, and suppresses failure details. It is not collected by ordinary test discovery and is not run automatically. A successful invocation verifies only that the configured endpoint responded consistently during that invocation; it is not a provider reliability benchmark, production readiness result, or final provider selection.

## Limitations

The adapter uses one HTTPS endpoint per instance, checks identity on every observation, and applies a per-request rather than total-operation timeout. It has no provider-specific authentication helper, retries, failover, polling, ingestion, persistence, background workers, or trading behavior. It does not establish clock synchronization, freshness, slot monotonicity, endpoint reliability, or correctness beyond the validated response for that invocation.
