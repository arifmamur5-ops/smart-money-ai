"""Immutable, provider-neutral contracts for an offline wallet dataset."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from smart_money_ai.solana_observation.models import NetworkIdentity

MAX_U64 = 2**64 - 1
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {character: index for index, character in enumerate(_BASE58)}
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def _required_string(value: object, name: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    if identifier and _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} has an invalid format")
    return value


def _version(value: object, name: str) -> str:
    _required_string(value, name)
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if _VERSION.fullmatch(value) is None:
        raise ValueError(f"{name} must use major.minor.patch format")
    return value


def _timestamp(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _slot(value: object, name: str = "slot") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not 0 <= value <= MAX_U64:
        raise ValueError(f"{name} must be in the unsigned 64-bit range")
    return value


def _base58_decode(value: str, name: str, expected_length: int) -> bytes:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value:
        raise ValueError(f"{name} must not be empty")
    number = 0
    try:
        for character in value:
            number = number * 58 + _BASE58_INDEX[character]
    except KeyError:
        raise ValueError(f"{name} must be base58 encoded") from None
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    leading_zeroes = len(value) - len(value.lstrip("1"))
    decoded = b"\0" * leading_zeroes + body
    if len(decoded) != expected_length or _base58_encode(decoded) != value:
        raise ValueError(f"{name} has an invalid decoded length or encoding")
    return decoded


def _base58_encode(value: bytes) -> str:
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _BASE58[remainder] + encoded
    zeroes = len(value) - len(value.lstrip(b"\0"))
    return "1" * zeroes + (encoded or ("" if zeroes else "1"))


def _network_key(network: NetworkIdentity) -> tuple[str, str]:
    return network.cluster, network.genesis_hash


@dataclass(frozen=True, slots=True)
class DatasetDefinition:
    """Versioned identity and inclusion policy for a researcher dataset."""

    dataset_id: str
    definition_version: str
    inclusion_rule_version: str
    schema_version: str

    def __post_init__(self) -> None:
        _required_string(self.dataset_id, "dataset_id", identifier=True)
        _version(self.definition_version, "definition_version")
        _version(self.inclusion_rule_version, "inclusion_rule_version")
        _version(self.schema_version, "schema_version")


class CoverageStatus(StrEnum):
    """Descriptive coverage state; it is not a completeness guarantee."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class MembershipDecision(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"


class EvidenceType(StrEnum):
    CURATED_SEED = "curated_seed"
    TRANSACTION_REFERENCE = "transaction_reference"
    ACCOUNT_OBSERVATION = "account_observation"
    OTHER = "other"


class RelationshipKind(StrEnum):
    """Explicit transaction relationship asserted from source evidence.

    These values label caller-supplied facts; the domain does not parse or
    independently verify transaction metadata.
    """

    # Explicit signer flag in transaction message/account metadata.
    SIGNER = "signer"
    # Explicit transaction fee payer; a fee payer may also be a signer.
    FEE_PAYER = "fee_payer"
    # Account referenced by a transaction instruction, not mere arbitrary
    # presence in a transaction account list.
    REFERENCED_ACCOUNT = "referenced_account"
    # Program ID actually invoked by an instruction, not an account passed
    # to another program.
    PROGRAM_INVOLVEMENT = "program_involvement"


@dataclass(frozen=True, slots=True)
class InstructionLocation:
    """Location of an instruction relationship; inner index is optional."""

    outer_index: int
    inner_index: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.outer_index, bool) or not isinstance(self.outer_index, int):
            raise TypeError("outer_index must be an integer")
        if self.outer_index < 0:
            raise ValueError("outer_index must be non-negative")
        if self.inner_index is not None:
            if isinstance(self.inner_index, bool) or not isinstance(self.inner_index, int):
                raise TypeError("inner_index must be an integer or None")
            if self.inner_index < 0:
                raise ValueError("inner_index must be non-negative")


@dataclass(frozen=True, slots=True)
class SourceRun:
    """One acquisition or researcher seed-registration operation."""

    run_id: str
    source_id: str
    operation: str
    acquired_at: datetime
    network: NetworkIdentity
    coverage_status: CoverageStatus = CoverageStatus.UNKNOWN
    window_start_slot: int | None = None
    window_end_slot: int | None = None

    def __post_init__(self) -> None:
        _required_string(self.run_id, "run_id", identifier=True)
        _required_string(self.source_id, "source_id", identifier=True)
        _required_string(self.operation, "operation")
        object.__setattr__(self, "acquired_at", _timestamp(self.acquired_at, "acquired_at"))
        if not isinstance(self.network, NetworkIdentity):
            raise TypeError("network must be a NetworkIdentity")
        if not isinstance(self.coverage_status, CoverageStatus):
            raise TypeError("coverage_status must be a CoverageStatus")
        if self.window_start_slot is not None:
            _slot(self.window_start_slot, "window_start_slot")
        if self.window_end_slot is not None:
            _slot(self.window_end_slot, "window_end_slot")
        if (self.window_start_slot is None) != (self.window_end_slot is None):
            raise ValueError("window start and end slots must be supplied together")
        if (self.window_start_slot is not None and self.window_end_slot is not None
                and self.window_start_slot > self.window_end_slot):
            raise ValueError("source run window start must not exceed its end")


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    """Source-specific evidence retained independently from normalized facts."""

    evidence_id: str
    source_run_id: str
    evidence_type: EvidenceType
    reference: str
    captured_at: datetime
    network: NetworkIdentity
    activity_fact_id: str | None = None
    researcher: str | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        _required_string(self.evidence_id, "evidence_id", identifier=True)
        _required_string(self.source_run_id, "source_run_id", identifier=True)
        _required_string(self.reference, "reference")
        if not isinstance(self.evidence_type, EvidenceType):
            raise TypeError("evidence_type must be an EvidenceType")
        object.__setattr__(self, "captured_at", _timestamp(self.captured_at, "captured_at"))
        if not isinstance(self.network, NetworkIdentity):
            raise TypeError("network must be a NetworkIdentity")
        if self.activity_fact_id is not None:
            _required_string(self.activity_fact_id, "activity_fact_id", identifier=True)
        if self.evidence_type is EvidenceType.CURATED_SEED:
            _required_string(self.researcher, "researcher")
            _required_string(self.rationale, "rationale")
            if self.activity_fact_id is not None:
                raise ValueError("curated seed evidence cannot claim an activity fact")
        elif self.researcher is not None or self.rationale is not None:
            raise ValueError("researcher and rationale are reserved for curated seed evidence")


@dataclass(frozen=True, slots=True)
class CandidateMembership:
    """A network-scoped address decision in a reviewed candidate pool."""

    network: NetworkIdentity
    address: str
    decision: MembershipDecision
    reason_code: str
    reason_version: str
    provenance_refs: tuple[str, ...]
    activity_fact_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.network, NetworkIdentity):
            raise TypeError("network must be a NetworkIdentity")
        _base58_decode(self.address, "address", 32)
        if not isinstance(self.decision, MembershipDecision):
            raise TypeError("decision must be a MembershipDecision")
        _required_string(self.reason_code, "reason_code", identifier=True)
        _version(self.reason_version, "reason_version")
        for field_name in ("provenance_refs", "activity_fact_refs"):
            refs = getattr(self, field_name)
            if not isinstance(refs, tuple):
                raise TypeError(f"{field_name} must be a tuple")
            for reference in refs:
                _required_string(reference, field_name, identifier=True)
            if len(set(refs)) != len(refs):
                raise ValueError(f"{field_name} must not contain duplicates")
            object.__setattr__(self, field_name, tuple(sorted(refs)))
        if not self.provenance_refs:
            raise ValueError("provenance_refs must contain at least one evidence reference")


@dataclass(frozen=True, slots=True)
class NormalizedActivityFact:
    """Caller-supplied address-to-transaction relationship, not ownership.

    Signers require explicit signer metadata; fee payers require explicit fee
    payer identification; referenced accounts require an instruction account
    reference; program involvement requires the invoked instruction program ID.
    Instruction location should identify the instruction when attributable;
    transaction-level signer/fee-payer facts may have no location. Multiple
    relationship facts may describe one address and transaction. The model
    validates shape only and does not establish chain truth, ownership,
    private-key control, identity, trader identity, or economic intent.
    """

    network: NetworkIdentity
    signature: str
    slot: int
    address: str
    relationship: RelationshipKind
    instruction_location: InstructionLocation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.network, NetworkIdentity):
            raise TypeError("network must be a NetworkIdentity")
        _base58_decode(self.signature, "signature", 64)
        _slot(self.slot)
        _base58_decode(self.address, "address", 32)
        if not isinstance(self.relationship, RelationshipKind):
            raise TypeError("relationship must be a RelationshipKind")
        if self.instruction_location is not None and not isinstance(
            self.instruction_location, InstructionLocation
        ):
            raise TypeError("instruction_location must be an InstructionLocation or None")

    @property
    def semantic_identity(self) -> tuple[object, ...]:
        location = self.instruction_location
        return (
            *_network_key(self.network), self.signature,
            None if location is None else location.outer_index,
            None if location is None else location.inner_index,
            self.address, self.relationship.value,
        )

    @property
    def fact_id(self) -> str:
        """Stable ID derived only from the semantic identity key."""
        raw = canonical_json_bytes({
            "network": {"cluster": self.network.cluster, "genesis_hash": self.network.genesis_hash},
            "signature": self.signature,
            "instruction_location": _location_dict(self.instruction_location),
            "address": self.address,
            "relationship": self.relationship.value,
        })
        return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    """Serialize JSON data using the project's canonical UTF-8 encoding."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _location_dict(location: InstructionLocation | None) -> dict[str, int | None] | None:
    if location is None:
        return None
    return {"outer_index": location.outer_index, "inner_index": location.inner_index}
