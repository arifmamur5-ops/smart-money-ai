"""Pure deterministic construction of finite wallet dataset snapshots."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeVar

from smart_money_ai.solana_observation.models import NetworkIdentity
from smart_money_ai.wallet_dataset.models import (
    CandidateMembership,
    CoverageStatus,
    DatasetDefinition,
    NormalizedActivityFact,
    SourceEvidence,
    SourceRun,
    _location_dict,
    _network_key,
    _required_string,
    _slot,
    _timestamp,
    canonical_json_bytes,
)

_Record = TypeVar("_Record")


@dataclass(frozen=True, slots=True)
class SnapshotManifest:
    """Snapshot metadata; generated_at is intentionally outside the digest."""

    schema_version: str
    definition: DatasetDefinition
    network: NetworkIdentity
    finalized_cutoff_slot: int
    commitment: Literal["finalized"]
    generated_at: datetime
    source_run_refs: tuple[str, ...]
    coverage_status: CoverageStatus
    candidate_count: int
    content_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.definition, DatasetDefinition):
            raise TypeError("definition must be a DatasetDefinition")
        if self.schema_version != self.definition.schema_version:
            raise ValueError("manifest and dataset definition schema versions must match")
        if not isinstance(self.network, NetworkIdentity):
            raise TypeError("network must be a NetworkIdentity")
        _slot(self.finalized_cutoff_slot, "finalized_cutoff_slot")
        if self.commitment != "finalized":
            raise ValueError('commitment must be "finalized"')
        object.__setattr__(self, "generated_at", _timestamp(self.generated_at, "generated_at"))
        if not isinstance(self.source_run_refs, tuple):
            raise TypeError("source_run_refs must be a tuple")
        for reference in self.source_run_refs:
            _required_string(reference, "source_run_refs", identifier=True)
        if tuple(sorted(set(self.source_run_refs))) != self.source_run_refs:
            raise ValueError("source_run_refs must be unique and sorted")
        if not isinstance(self.coverage_status, CoverageStatus):
            raise TypeError("coverage_status must be a CoverageStatus")
        if isinstance(self.candidate_count, bool) or not isinstance(self.candidate_count, int):
            raise TypeError("candidate_count must be an integer")
        if self.candidate_count < 0:
            raise ValueError("candidate_count must be non-negative")
        if not isinstance(self.content_digest, str) or re.fullmatch(r"[0-9a-f]{64}", self.content_digest) is None:
            raise ValueError("content_digest must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True, slots=True)
class DatasetSnapshot:
    """Immutable records and manifest produced by :func:`build_snapshot`."""

    manifest: SnapshotManifest
    candidates: tuple[CandidateMembership, ...]
    source_runs: tuple[SourceRun, ...]
    source_evidence: tuple[SourceEvidence, ...]
    activity_facts: tuple[NormalizedActivityFact, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, SnapshotManifest):
            raise TypeError("manifest must be a SnapshotManifest")
        candidates, runs, evidence, facts = _normalize_snapshot_records(
            network=self.manifest.network,
            finalized_cutoff_slot=self.manifest.finalized_cutoff_slot,
            coverage_status=self.manifest.coverage_status,
            candidates=self.candidates,
            source_runs=self.source_runs,
            source_evidence=self.source_evidence,
            activity_facts=self.activity_facts,
        )
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "source_runs", runs)
        object.__setattr__(self, "source_evidence", evidence)
        object.__setattr__(self, "activity_facts", facts)
        if self.manifest.candidate_count != len(candidates):
            raise ValueError("manifest candidate_count does not match snapshot candidates")
        expected_run_refs = tuple(sorted(run.run_id for run in runs))
        if self.manifest.source_run_refs != expected_run_refs:
            raise ValueError("manifest source_run_refs do not match snapshot source runs")
        digest = hashlib.sha256(serialize_snapshot_content(self)).hexdigest()
        if digest != self.manifest.content_digest:
            raise ValueError("manifest content_digest does not match snapshot content")


def _network_dict(network: NetworkIdentity) -> dict[str, str]:
    return {"cluster": network.cluster, "genesis_hash": network.genesis_hash}


def _definition_dict(definition: DatasetDefinition) -> dict[str, str]:
    return {
        "dataset_id": definition.dataset_id,
        "definition_version": definition.definition_version,
        "inclusion_rule_version": definition.inclusion_rule_version,
        "schema_version": definition.schema_version,
    }


def _time(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_dict(run: SourceRun) -> dict[str, object]:
    return {
        "run_id": run.run_id,
        "source_id": run.source_id,
        "operation": run.operation,
        "acquired_at": _time(run.acquired_at),
        "network": _network_dict(run.network),
        "coverage_status": run.coverage_status.value,
        "window_start_slot": run.window_start_slot,
        "window_end_slot": run.window_end_slot,
    }


def _evidence_dict(evidence: SourceEvidence) -> dict[str, object]:
    return {
        "evidence_id": evidence.evidence_id,
        "source_run_id": evidence.source_run_id,
        "evidence_type": evidence.evidence_type.value,
        "reference": evidence.reference,
        "captured_at": _time(evidence.captured_at),
        "network": _network_dict(evidence.network),
        "activity_fact_id": evidence.activity_fact_id,
        "researcher": evidence.researcher,
        "rationale": evidence.rationale,
    }


def _candidate_dict(candidate: CandidateMembership) -> dict[str, object]:
    return {
        "network": _network_dict(candidate.network),
        "address": candidate.address,
        "decision": candidate.decision.value,
        "reason_code": candidate.reason_code,
        "reason_version": candidate.reason_version,
        "provenance_refs": list(candidate.provenance_refs),
        "activity_fact_refs": list(candidate.activity_fact_refs),
    }


def _activity_dict(fact: NormalizedActivityFact) -> dict[str, object]:
    return {
        "fact_id": fact.fact_id,
        "network": _network_dict(fact.network),
        "signature": fact.signature,
        "slot": fact.slot,
        "address": fact.address,
        "relationship": fact.relationship.value,
        "instruction_location": _location_dict(fact.instruction_location),
    }


def _normalize_snapshot_records(
    *,
    network: NetworkIdentity,
    finalized_cutoff_slot: int,
    coverage_status: CoverageStatus,
    candidates: tuple[CandidateMembership, ...],
    source_runs: tuple[SourceRun, ...],
    source_evidence: tuple[SourceEvidence, ...],
    activity_facts: tuple[NormalizedActivityFact, ...],
) -> tuple[
    tuple[CandidateMembership, ...],
    tuple[SourceRun, ...],
    tuple[SourceEvidence, ...],
    tuple[NormalizedActivityFact, ...],
]:
    """Shared type, identity, graph, network, cutoff, and coverage validation."""
    groups = (
        ("candidates", candidates, CandidateMembership),
        ("source_runs", source_runs, SourceRun),
        ("source_evidence", source_evidence, SourceEvidence),
        ("activity_facts", activity_facts, NormalizedActivityFact),
    )
    for name, records, expected_type in groups:
        if not isinstance(records, tuple):
            raise TypeError(f"{name} must be a tuple")
        if any(not isinstance(record, expected_type) for record in records):
            raise TypeError(f"{name} contains an invalid record type")

    runs = _deduplicate(source_runs, lambda item: item.run_id, "source run")
    evidence = _deduplicate(source_evidence, lambda item: item.evidence_id, "source evidence")
    memberships = _deduplicate(
        candidates, lambda item: (*_network_key(item.network), item.address), "candidate membership"
    )
    facts = _deduplicate(activity_facts, lambda item: item.semantic_identity, "activity fact")

    _validate_coverage_claim(coverage_status, runs)
    for run in runs:
        _require_network(run.network, network, "source run")
    run_ids = {run.run_id for run in runs}
    for item in evidence:
        _require_network(item.network, network, "source evidence")
        if item.source_run_id not in run_ids:
            raise ValueError(f"source evidence refers to unknown source run {item.source_run_id!r}")

    fact_by_id = {fact.fact_id: fact for fact in facts}
    for fact in facts:
        _require_network(fact.network, network, "activity fact")
        if fact.slot > finalized_cutoff_slot:
            raise ValueError("activity fact slot exceeds the finalized snapshot cutoff")

    evidence_by_id = {item.evidence_id: item for item in evidence}
    for item in memberships:
        _require_network(item.network, network, "candidate membership")
        for evidence_ref in item.provenance_refs:
            if evidence_ref not in evidence_by_id:
                raise ValueError(f"candidate refers to unknown source evidence {evidence_ref!r}")
        for fact_ref in item.activity_fact_refs:
            fact = fact_by_id.get(fact_ref)
            if fact is None:
                raise ValueError(f"candidate refers to unknown activity fact {fact_ref!r}")
            if fact.address != item.address or fact.network != item.network:
                raise ValueError("candidate activity fact must refer to the same network-scoped address")

    for item in evidence:
        if item.activity_fact_id is not None and item.activity_fact_id not in fact_by_id:
            raise ValueError(f"source evidence refers to unknown activity fact {item.activity_fact_id!r}")
    supported_fact_ids = {item.activity_fact_id for item in evidence if item.activity_fact_id is not None}
    if any(fact.fact_id not in supported_fact_ids for fact in facts):
        raise ValueError("every normalized activity fact must retain at least one source evidence reference")

    return memberships, runs, evidence, facts


def _validate_coverage_claim(
    requested: CoverageStatus, source_runs: tuple[SourceRun, ...]
) -> None:
    """Reject snapshot claims stronger than the aggregate source-run status."""
    if not isinstance(requested, CoverageStatus):
        raise TypeError("coverage_status must be a CoverageStatus")
    if requested is CoverageStatus.UNKNOWN:
        return
    if not source_runs:
        raise ValueError("snapshots without source runs must have unknown coverage")

    statuses = {run.coverage_status for run in source_runs}
    if CoverageStatus.UNKNOWN in statuses:
        supported = CoverageStatus.UNKNOWN
    elif CoverageStatus.PARTIAL in statuses:
        supported = CoverageStatus.PARTIAL
    else:
        supported = CoverageStatus.COMPLETE
    if _coverage_rank(requested) > _coverage_rank(supported):
        raise ValueError("snapshot coverage cannot exceed source-run coverage")


def _coverage_rank(status: CoverageStatus) -> int:
    return {
        CoverageStatus.UNKNOWN: 0,
        CoverageStatus.PARTIAL: 1,
        CoverageStatus.COMPLETE: 2,
    }[status]


def canonical_snapshot_content(snapshot: DatasetSnapshot) -> dict[str, object]:
    """Return the exact digest-covered JSON object (excluding volatile metadata)."""
    return {
        "schema_version": snapshot.manifest.schema_version,
        "dataset_definition": _definition_dict(snapshot.manifest.definition),
        "network": _network_dict(snapshot.manifest.network),
        "finalized_cutoff": {
            "slot": snapshot.manifest.finalized_cutoff_slot,
            "commitment": snapshot.manifest.commitment,
        },
        "coverage_status": snapshot.manifest.coverage_status.value,
        "candidate_count": snapshot.manifest.candidate_count,
        "candidates": [_candidate_dict(item) for item in snapshot.candidates],
        "source_runs": [_run_dict(item) for item in snapshot.source_runs],
        "source_evidence": [_evidence_dict(item) for item in snapshot.source_evidence],
        "activity_facts": [_activity_dict(item) for item in snapshot.activity_facts],
    }


def serialize_snapshot_content(snapshot: DatasetSnapshot) -> bytes:
    """Return canonical UTF-8 JSON bytes covered by ``content_digest``."""
    return canonical_json_bytes(canonical_snapshot_content(snapshot))


def build_snapshot(
    *,
    definition: DatasetDefinition,
    network: NetworkIdentity,
    finalized_cutoff_slot: int,
    generated_at: datetime,
    candidates: tuple[CandidateMembership, ...] = (),
    source_runs: tuple[SourceRun, ...] = (),
    source_evidence: tuple[SourceEvidence, ...] = (),
    activity_facts: tuple[NormalizedActivityFact, ...] = (),
    coverage_status: CoverageStatus = CoverageStatus.UNKNOWN,
) -> DatasetSnapshot:
    """Validate, deterministically deduplicate/order, and digest offline inputs."""
    if not isinstance(definition, DatasetDefinition):
        raise TypeError("definition must be a DatasetDefinition")
    if not isinstance(network, NetworkIdentity):
        raise TypeError("network must be a NetworkIdentity")
    cutoff = _slot(finalized_cutoff_slot, "finalized_cutoff_slot")
    timestamp = _timestamp(generated_at, "generated_at")
    memberships, runs, evidence, facts = _normalize_snapshot_records(
        network=network,
        finalized_cutoff_slot=cutoff,
        coverage_status=coverage_status,
        candidates=candidates,
        source_runs=source_runs,
        source_evidence=source_evidence,
        activity_facts=activity_facts,
    )

    run_refs = tuple(sorted(run.run_id for run in runs))
    manifest_without_digest = {
        "schema_version": definition.schema_version,
        "dataset_definition": _definition_dict(definition),
        "network": _network_dict(network),
        "finalized_cutoff": {"slot": cutoff, "commitment": "finalized"},
        "coverage_status": coverage_status.value,
        "candidate_count": len(memberships),
        "candidates": [_candidate_dict(item) for item in memberships],
        "source_runs": [_run_dict(item) for item in runs],
        "source_evidence": [_evidence_dict(item) for item in evidence],
        "activity_facts": [_activity_dict(item) for item in facts],
    }
    digest = hashlib.sha256(canonical_json_bytes(manifest_without_digest)).hexdigest()
    manifest = SnapshotManifest(
        schema_version=definition.schema_version,
        definition=definition,
        network=network,
        finalized_cutoff_slot=cutoff,
        commitment="finalized",
        generated_at=timestamp,
        source_run_refs=run_refs,
        coverage_status=coverage_status,
        candidate_count=len(memberships),
        content_digest=digest,
    )
    snapshot = DatasetSnapshot(manifest, memberships, runs, evidence, facts)
    return snapshot


def _deduplicate(
    records: tuple[_Record, ...], identity: Callable[[_Record], Hashable], label: str
) -> tuple[_Record, ...]:
    retained: dict[Hashable, _Record] = {}
    for record in records:
        key = identity(record)
        previous = retained.get(key)
        if previous is None:
            retained[key] = record
        elif previous != record:
            raise ValueError(f"conflicting {label} content for identity {key!r}")
    return tuple(sorted(retained.values(), key=_canonical_record_bytes))


def _canonical_record_bytes(record: object) -> bytes:
    if isinstance(record, CandidateMembership):
        value = _candidate_dict(record)
    elif isinstance(record, SourceRun):
        value = _run_dict(record)
    elif isinstance(record, SourceEvidence):
        value = _evidence_dict(record)
    elif isinstance(record, NormalizedActivityFact):
        value = _activity_dict(record)
    else:
        raise TypeError("unsupported snapshot record")
    return canonical_json_bytes(value)


def _require_network(actual: NetworkIdentity, expected: NetworkIdentity, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} network identity does not match the snapshot network")
