# Live Finalized Slot Adapter Implementation Specification

**Status:** M4 implementation specification; no live adapter is implemented by this document.

## Purpose and compatibility boundary

Specify the smallest synchronous HTTPS JSON-RPC adapter that implements the existing `FinalizedSlotObserver` protocol for one finalized-slot observation. The adapter must preserve the M1 `NetworkIdentity`, `ObservationSource`, `FinalizedSlotObservation`, `ObservationError`, and `FinalizedSlotObserver` contracts. It must not change the domain model or application wiring.

The endpoint is explicitly supplied to the adapter. No provider is selected here; provider-specific endpoint shape and authentication remain configuration-boundary details. Only the provider-neutral `source_id` enters the domain observation.

## Configuration inputs

The adapter needs:

- An explicit endpoint URL whose scheme is `https`.
- An expected `NetworkIdentity`.
- A provider-neutral `ObservationSource` / `source_id`.
- An explicit positive request timeout in seconds.
- A clock callable for deterministic tests; production default must return an aware local UTC timestamp.

Reject a non-HTTPS or malformed endpoint and invalid timeout during construction or configuration validation. Do not derive, discover, or fall back to another endpoint. Credentials may be embedded by a provider in the URL or supplied through a provider-supported header, but the implementation must never expose them in logs, exception messages, or test output. Endpoint credential storage and rotation are separate configuration decisions; this specification does not add environment settings or dependency wiring.

## Request sequence and behavior

For each call to `get_finalized_slot()`:

1. POST a JSON-RPC 2.0 request for `getGenesisHash` with an empty `params` array and a request ID.
2. Validate the HTTP response and JSON-RPC envelope. Require a valid string result. Compare it exactly with the configured expected `network.genesis_hash`. If it does not match, raise `ObservationError` and do not request the slot.
3. POST a JSON-RPC 2.0 request for `getSlot`, passing `[{"commitment":"finalized"}]` and a request ID.
4. Validate the HTTP response and JSON-RPC envelope. Require an integer slot result, reject booleans and negative values, and reject values greater than `2**64 - 1`. Solana defines the response as `u64`; this upper bound is adapter-specific response validation. The broader M1 domain model remains unchanged and continues to accept any non-negative integer.
5. Immediately after receiving and validating the successful slot response, call the injected clock at the adapter boundary. Require a timezone-aware `datetime`; normalize it to UTC through the existing model behavior. A naive or invalid clock result must fail as `ObservationError`, never produce a fabricated observation.
6. Return the existing `FinalizedSlotObservation` with the configured network, slot, `commitment="finalized"`, configured source, and captured `observed_at`.

The specification chooses to check genesis on every adapter call. This avoids adding cached network identity or connection lifecycle state and makes each observation independently network-verified. It means two RPC calls per observation; provider cost/quotas must account for both. This is a specification-level choice, not behavior tested against a production endpoint.

The `cluster` field is a configured label; `getGenesisHash` verifies the network by hash only. The adapter does not infer the cluster from a hash or verify that a caller-supplied label/hash pair is canonical beyond the configured exact hash comparison.

## HTTP and JSON-RPC validation

Use HTTPS POST with `Content-Type: application/json` and a small JSON-RPC request body. Validate at least:

- Successful 2xx HTTP status.
- Redirect handling must not downgrade HTTPS to HTTP. The simplest policy is to reject redirects. If redirects are supported, validate the scheme of every redirect target and ensure credentials are not forwarded to an untrusted host.
- JSON body parses as an object.
- `jsonrpc` is `"2.0"` and the response `id` matches the request ID.
- A successful response has a valid `result` and no JSON-RPC `error` object.
- A JSON-RPC error object, missing result, wrong result type, or malformed response is a failure.
- `getGenesisHash` result is a non-empty string matching the expected hash exactly.
- `getSlot` result is an integer in the Solana `u64` range `0 <= slot <= 2**64 - 1`. Reject booleans, negative integers, out-of-range integers, floats, strings, and all other types. This check belongs to the RPC adapter; do not change the M1 domain model.

Do not parse provider-specific success envelopes, accept a different commitment, or silently coerce strings/floats/bools into slot integers. Do not treat HTTP 200 by itself as proof of RPC success.

## Timeout, error, and security policy

- Use a configurable finite timeout for each HTTP request. There is no automatic retry.
- No provider failover, hidden second endpoint, polling, scheduler, or subscription behavior.
- Map transport errors, timeouts, rejected/unsafe redirects, non-2xx status, malformed JSON, invalid JSON-RPC envelope, JSON-RPC error, invalid result, and genesis mismatch to the existing `ObservationError`.
- Exception messages may identify the operation and safe category/status, but must not include the endpoint URL, credential, authorization header, response body, or raw low-level exception text. Suppress chained exception text if it could reveal the URL or credential.
- Do not log request/response bodies or endpoint values. If logging is later added, log only safe operation metadata and sanitized status/error categories.
- Reject redirects as the simplest safe policy. If redirect support is introduced, never follow a redirect from HTTPS to HTTP; validate the scheme of every destination and do not forward credentials to a host that is not explicitly trusted. Redirect errors and diagnostics must not expose URLs or credentials.
- Preserve normal TLS certificate verification; never disable it to make an endpoint work.

The specification chooses a finite timeout per HTTP request. Thus the total `get_finalized_slot()` duration can approach two timeout periods plus local processing. This is a specification-level choice, not a production-tested operational objective; whether a stricter total-operation deadline is needed remains open.

## Dependency and transport approach

Prefer Python's standard-library synchronous HTTPS/JSON facilities or an already-declared dependency if it provides a suitable synchronous client and predictable timeouts. The current project directly declares FastAPI, python-dotenv, and Uvicorn; it does not directly declare an HTTP client for this purpose. If a new HTTP dependency is needed for connection reuse, timeout control, or reliable response handling, document the concrete gap and obtain separate approval before adding it. Do not add a dependency as part of the M4 implementation without that approval.

Keep transport handling inside this adapter. Unit tests may mock the standard-library transport call and inject a fixed clock; do not add a generic transport framework or change the public observation protocol.

## Unit test requirements

All tests must be deterministic and run without network access. Use the existing `unittest` conventions, mocked transport responses, and fixed aware timestamps. Cover:

1. A valid finalized slot response returns the existing observation type with configured network/source and the returned slot.
2. Requests use JSON-RPC 2.0 and the correct method names, IDs, and parameters: `getGenesisHash` with `[]`, then `getSlot` with commitment `finalized`.
3. A matching genesis hash proceeds to `getSlot`; mismatch raises `ObservationError` and prevents the slot request.
4. HTTP non-2xx failure raises `ObservationError`.
5. Timeout raises `ObservationError`.
6. Malformed JSON raises `ObservationError`.
7. JSON-RPC `error` response, invalid version/ID, or missing result raises `ObservationError`.
8. Missing, wrong-type, boolean, negative, and greater-than-`2**64 - 1` slot results raise `ObservationError`; floats and strings are rejected without coercion.
9. A naive or invalid injected observation timestamp raises `ObservationError`; a fixed offset-aware timestamp is normalized to UTC in the result.
10. Credential redaction: simulate an endpoint and low-level error containing a sentinel secret, then assert exception text/log output does not contain the URL, token, authorization value, or response body.
11. Transport mocking is deterministic and asserts no real network call is attempted.
12. Any transport failure during genesis verification also fails without requesting a slot or returning an observation.

## Opt-in live endpoint smoke test

Provide a separately invoked, explicitly opt-in integration smoke test against a real provider endpoint. It must not be discovered or run by ordinary unit-test discovery or `make test`. The test should:

- Require the caller to provide an endpoint through a secure local mechanism; never create accounts or provision credentials automatically.
- Call only `getGenesisHash` and finalized `getSlot` over HTTPS.
- Compare the returned genesis hash to an explicitly expected identity.
- Have a finite timeout and no retries/failover.
- Print only pass/fail and safe latency/status summaries; never print endpoint URLs, credentials, headers, raw response bodies, or exception strings that may contain secrets.
- Be run manually after provider selection and before enabling the adapter in any application flow.

The smoke test verifies only that one endpoint behaved as expected at that time. It is not a reliability test or production readiness guarantee.

## Acceptance criteria

The implementation is acceptable when it:

- Implements the existing synchronous protocol without changing its signature or M1 models.
- Uses an explicit HTTPS endpoint, configured provider-neutral source identity, expected network identity, and explicit timeout.
- Verifies the genesis hash before obtaining the slot and requests `finalized` commitment explicitly.
- Validates HTTP, redirects, JSON, JSON-RPC envelope, identity, and the full `u64` slot range without unsafe coercion.
- Captures local aware UTC `observed_at` at the adapter boundary immediately after a valid slot response.
- Raises the existing `ObservationError` for all specified operational and response failures, with credential-safe messages.
- Is fully unit-testable without live networking and keeps provider-specific details within adapter/configuration boundaries.
- Adds no persistence, retries, failover, endpoints, scheduling, streaming, or application wiring.

## Decisions still open

Before implementation, settle:

- Which standard-library transport or already-declared dependency meets timeout, TLS, response decoding, and test-mocking needs; approve any new dependency separately.
- The secure endpoint/credential configuration source, URL/header authentication form, and redaction method for each selected provider.
- Which expected cluster labels and authoritative genesis hashes are supported.
- What safe error/status metadata may be logged, if logging is introduced later.
- Whether operations require an overall deadline shorter than the maximum combined duration of the two specified per-request timeouts.

The specification-level choices to verify genesis on every call, apply a finite timeout to each request, reject or safely validate redirects, and enforce the RPC `u64` range are written requirements for the future implementation. They are not claims of production testing. No provider, credential mechanism, dependency, or production SLO is selected here.
