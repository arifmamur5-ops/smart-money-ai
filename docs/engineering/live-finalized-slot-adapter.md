# Live Finalized Slot Adapter (M5)

**Status:** Implemented as a provider-neutral, read-only HTTPS JSON-RPC adapter. No provider has been selected and no live endpoint has been verified by this implementation.

## Purpose and boundary

`LiveFinalizedSlotAdapter` implements the existing synchronous `FinalizedSlotObserver` contract. It performs one `getGenesisHash` request and, if the exact configured hash matches, one `getSlot` request at `finalized` commitment. It returns the existing M1 `FinalizedSlotObservation`; it adds no provider-specific model fields and does not infer the configured cluster label from the hash.

Construction requires an HTTPS endpoint, a `NetworkIdentity`, a non-empty provider-neutral `source_id`, and a finite positive timeout in seconds. A clock callable may be supplied for deterministic use; the default is local aware UTC time. The adapter does not take credentials through a separate mechanism; endpoint URL authentication supported by an RPC service remains the caller's configuration responsibility.

Each request has its own timeout. The full operation uses two sequential requests, so wall-clock duration may approach twice the configured timeout plus local processing. The timestamp is captured after both successful responses and normalized to UTC by the existing M1 model.

## Validation and errors

The adapter validates HTTPS URL structure, HTTP success, UTF-8 JSON, the JSON-RPC 2.0 envelope and matching request ID, result presence, exact genesis hash identity, and an integer slot in `0..2**64-1` (with booleans rejected). Failures in transport, HTTP, redirects, response parsing, JSON-RPC, identity, slot validation, and clock output raise `ObservationError`. Configuration argument errors follow the existing model convention of `TypeError` or `ValueError` at construction.

The standard-library `urllib` transport verifies TLS certificates using its normal default context. Redirects are rejected before they can be followed, so credentials in the endpoint are not sent to a redirected destination. Error messages do not include the endpoint, credentials, response body, or underlying exception text; no request or response logging is performed. There are no retries.

Each individual RPC response body is read with a 64 KiB upper bound. The adapter reads at most one byte beyond that bound to detect oversize responses and rejects them without parsing or including response content in the error; there is no aggregate byte limit across the two-request operation. A normally returned response is context-managed, so it is closed on success, non-success status, oversized-body rejection, and read failures handled by the context manager. `urllib.error.HTTPError` responses are explicitly closed before being mapped to a sanitized `ObservationError`; redirect responses are closed by the redirect handler before rejection. A cleanup `OSError` while closing an `HTTPError` does not replace the sanitized mapping for the original HTTP failure. Transport failures such as `URLError` that do not provide an acquired response have no response resource to close.

## Validation commands

Run ordinary tests with `make test` (or `uv run --locked python -m unittest discover -s tests -v`). Tests inject the HTTP transport and do not access the public internet.

An optional live smoke check can be run manually after setting `SOLANA_RPC_ENDPOINT`, `SOLANA_CLUSTER`, `SOLANA_GENESIS_HASH`, and `SOLANA_RPC_TIMEOUT_SECONDS` in the local environment or `.env`. The script uses the same `load_settings()` configuration as the application; `SOLANA_RPC_SOURCE_ID` defaults to `application-rpc`:

```sh
python -m scripts.solana_rpc_smoke
```

It invokes only `getGenesisHash` and finalized `getSlot`, prints safe observation fields on success, and suppresses failure details. It is not collected by ordinary test discovery and is not run automatically. A successful invocation verifies only that the configured endpoint responded consistently during that invocation; it is not a provider reliability benchmark, production readiness result, or final provider selection. See the [provider qualification framework](solana-provider-qualification.md) before using it as qualification evidence.

## Limitations

The adapter uses one HTTPS endpoint per instance, checks identity on every observation, and applies a per-request rather than total-operation timeout. It has no provider-specific authentication helper, retries, failover, polling, ingestion, persistence, background workers, or trading behavior. It does not establish clock synchronization, freshness, slot monotonicity, endpoint reliability, or correctness beyond the validated response for that invocation.
