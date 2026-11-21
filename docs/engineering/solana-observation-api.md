# Solana Finalized Slot Observation API (M6)

**Status:** Implemented as a minimal read-only application endpoint. Provider selection and live endpoint verification remain open.

## Runtime configuration

The API uses the existing `LiveFinalizedSlotAdapter`. Configure all four values below to enable it:

| Environment variable | Meaning |
| --- | --- |
| `SOLANA_RPC_ENDPOINT` | Explicit HTTPS JSON-RPC endpoint; treat it as secret if it contains credentials. |
| `SOLANA_CLUSTER` | Caller-supplied cluster label. It is not inferred from the genesis hash. |
| `SOLANA_GENESIS_HASH` | Expected genesis hash verified against the endpoint on each observation. |
| `SOLANA_RPC_TIMEOUT_SECONDS` | Positive finite timeout in seconds for each of the two RPC requests. |

`SOLANA_RPC_SOURCE_ID` is optional and defaults to the provider-neutral value `application-rpc`. No endpoint, cluster, or genesis hash is supplied by default. Endpoint credentials belong in a local ignored `.env` file or the process environment; never commit them.

With all four required values absent, application startup succeeds and the API returns HTTP 503 with code `solana_rpc_not_configured`. Partial or invalid configuration also leaves startup available and returns sanitized HTTP 503 with code `solana_rpc_configuration_invalid`. Adapter construction and configuration validation make no RPC request. A request to the observation endpoint is the only operation that performs RPC calls.

## Endpoint and response contract

`GET /solana/observations/finalized-slot` performs one genesis verification and one `getSlot` request with `finalized` commitment. A successful response has this shape:

```json
{
  "network": {
    "cluster": "devnet",
    "genesis_hash": "configured-genesis-hash"
  },
  "slot": 123,
  "commitment": "finalized",
  "source": {
    "source_id": "application-rpc"
  },
  "observed_at": "2026-05-06T07:08:09+00:00"
}
```

`observed_at` is the adapter's local UTC-normalized receipt time, not a Solana block timestamp. The response preserves configured identity and M1 observation fields. It does not expose the RPC endpoint or provider response.

## Error responses

- **503 `solana_rpc_not_configured`:** no RPC configuration was supplied.
- **503 `solana_rpc_configuration_invalid`:** the required configuration is partial or invalid.
- **502 `solana_observation_failed`:** the adapter reported an observation, transport, identity, or provider response failure.
- **500 `internal_error`:** an unexpected application failure occurred; implementation details are suppressed.

Responses contain stable error codes and generic messages. Endpoint credentials, raw RPC responses, and low-level exception details are not returned. No request or provider call happens at application startup. The existing `GET /health` behavior is unchanged and does not report RPC readiness.

## Boundary and limitations

The route is synchronous at the observer boundary and performs RPC reads only for an explicit GET request. It does not implement retries, polling, persistence, ingestion, provider selection/failover, block timestamp lookup, or trading. It does not establish endpoint reliability, freshness, or production readiness. The API and adapter have deterministic unit tests; no live RPC endpoint is validated by these tests.
