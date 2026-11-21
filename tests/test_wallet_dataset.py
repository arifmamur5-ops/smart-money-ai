"""Offline deterministic tests for the wallet dataset domain and snapshots."""

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from smart_money_ai.solana_observation import NetworkIdentity
from smart_money_ai.wallet_dataset import (
    MAX_U64,
    CandidateMembership,
    CoverageStatus,
    DatasetDefinition,
    DatasetSnapshot,
    EvidenceType,
    InstructionLocation,
    MembershipDecision,
    NormalizedActivityFact,
    RelationshipKind,
    SourceEvidence,
    SourceRun,
    SnapshotManifest,
    build_snapshot,
    serialize_snapshot_content,
)


def _b58(data: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(data, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    zeroes = len(data) - len(data.lstrip(b"\0"))
    return "1" * zeroes + encoded


ADDRESS = _b58(bytes(range(32)))
OTHER_ADDRESS = _b58(bytes(reversed(range(32))))
SIGNATURE = _b58(bytes(range(64)))
STAMP = datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc)


class WalletDatasetContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = NetworkIdentity("devnet", "genesis-a")
        self.definition = DatasetDefinition("research-cohort", "1.0.0", "1.0.0", "1.0.0")

    def run_record(self, run_id: str = "seed-run", network: NetworkIdentity | None = None) -> SourceRun:
        return SourceRun(
            run_id=run_id,
            source_id="researcher-curated",
            operation="register curated address seeds",
            acquired_at=STAMP,
            network=network or self.network,
            coverage_status=CoverageStatus.UNKNOWN,
        )

    def evidence(
        self,
        evidence_id: str = "seed-evidence",
        run_id: str = "seed-run",
        *,
        evidence_type: EvidenceType = EvidenceType.CURATED_SEED,
        network: NetworkIdentity | None = None,
        activity_fact_id: str | None = None,
    ) -> SourceEvidence:
        return SourceEvidence(
            evidence_id=evidence_id,
            source_run_id=run_id,
            evidence_type=evidence_type,
            reference="research-notes:entry-1",
            captured_at=STAMP,
            network=network or self.network,
            activity_fact_id=activity_fact_id,
            researcher="researcher-1" if evidence_type is EvidenceType.CURATED_SEED else None,
            rationale="included for study" if evidence_type is EvidenceType.CURATED_SEED else None,
        )

    def candidate(self, **changes: object) -> CandidateMembership:
        values: dict[str, object] = {
            "network": self.network,
            "address": ADDRESS,
            "decision": MembershipDecision.INCLUDE,
            "reason_code": "research_seed",
            "reason_version": "1.0.0",
            "provenance_refs": ("seed-evidence",),
        }
        values.update(changes)
        return CandidateMembership(**values)  # type: ignore[arg-type]

    def test_network_identity_is_required_and_preserves_both_labels(self) -> None:
        identity = NetworkIdentity(" custom-cluster ", "genesis")
        self.assertEqual(identity.cluster, " custom-cluster ")
        self.assertEqual(identity.genesis_hash, "genesis")
        with self.assertRaises(ValueError):
            NetworkIdentity(" ", "genesis")
        with self.assertRaises(ValueError):
            NetworkIdentity("devnet", "")

    def test_definition_requires_stable_versions_and_identifier(self) -> None:
        for version in ("1", "v1.0.0", "01.0.0", "1.0"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                DatasetDefinition("cohort", version, "1.0.0", "1.0.0")
        with self.assertRaises(ValueError):
            DatasetDefinition(" ", "1.0.0", "1.0.0", "1.0.0")

    def test_valid_address_and_curated_seed_need_no_transaction(self) -> None:
        evidence = self.evidence()
        candidate = self.candidate()
        snapshot = build_snapshot(
            definition=self.definition,
            network=self.network,
            finalized_cutoff_slot=0,
            generated_at=STAMP,
            candidates=(candidate,),
            source_runs=(self.run_record(),),
            source_evidence=(evidence,),
        )
        self.assertEqual(snapshot.manifest.candidate_count, 1)
        self.assertEqual(snapshot.candidates[0].activity_fact_refs, ())
        self.assertEqual(snapshot.source_evidence[0].evidence_type, EvidenceType.CURATED_SEED)
        self.assertEqual(snapshot.source_evidence[0].rationale, "included for study")

    def test_invalid_address_encoding_and_decoded_length(self) -> None:
        for address in ("", "0" * 32, "111", 123):
            with self.subTest(address=address), self.assertRaises((TypeError, ValueError)):
                self.candidate(address=address)

    def test_inclusion_and_exclusion_decisions_and_reason_validation(self) -> None:
        self.assertEqual(self.candidate().decision, MembershipDecision.INCLUDE)
        excluded = self.candidate(decision=MembershipDecision.EXCLUDE, reason_code="out_of_scope")
        self.assertEqual(excluded.decision, MembershipDecision.EXCLUDE)
        for decision in ("include", "reject", None):
            with self.subTest(decision=decision), self.assertRaises(TypeError):
                self.candidate(decision=decision)
        for reason in ("", "has space"):
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                self.candidate(reason_code=reason)
        with self.assertRaises(ValueError):
            self.candidate(reason_version="v1")

    def test_timezone_aware_values_normalize_to_utc_and_naive_values_fail(self) -> None:
        offset = STAMP.astimezone(timezone(timedelta(hours=7)))
        run = replace(self.run_record(), acquired_at=offset)
        self.assertEqual(run.acquired_at, STAMP)
        with self.assertRaises(ValueError):
            SourceRun("run", "source", "operation", datetime(2026, 1, 1), self.network)

    def test_slots_validate_type_boundaries_and_cutoff(self) -> None:
        for slot, error in ((True, TypeError), (-1, ValueError), (MAX_U64 + 1, ValueError), (1.5, TypeError)):
            with self.subTest(slot=slot), self.assertRaises(error):
                build_snapshot(definition=self.definition, network=self.network,
                               finalized_cutoff_slot=slot, generated_at=STAMP)
        fact = self.fact(slot=MAX_U64)
        self.assertEqual(fact.slot, MAX_U64)
        for slot, error in ((True, TypeError), (-1, ValueError), (MAX_U64 + 1, ValueError)):
            with self.subTest(activity_slot=slot), self.assertRaises(error):
                self.fact(slot=slot)
        with self.assertRaises(ValueError):
            build_snapshot(definition=self.definition, network=self.network,
                           finalized_cutoff_slot=MAX_U64 - 1, generated_at=STAMP,
                           source_runs=(self.run_record(),),
                           source_evidence=(self.evidence("activity", evidence_type=EvidenceType.TRANSACTION_REFERENCE,
                                                          activity_fact_id=fact.fact_id),),
                           activity_facts=(fact,))

    def fact(self, **changes: object) -> NormalizedActivityFact:
        values: dict[str, object] = {
            "network": self.network,
            "signature": SIGNATURE,
            "slot": 8,
            "address": ADDRESS,
            "relationship": RelationshipKind.REFERENCED_ACCOUNT,
        }
        values.update(changes)
        return NormalizedActivityFact(**values)  # type: ignore[arg-type]

    def test_activity_signature_relationship_and_instruction_location(self) -> None:
        fact = self.fact(instruction_location=InstructionLocation(0, 1))
        self.assertEqual(fact.instruction_location, InstructionLocation(0, 1))
        self.assertNotEqual(fact.fact_id, self.fact().fact_id)
        self.assertNotEqual(fact.fact_id, self.fact(relationship=RelationshipKind.SIGNER).fact_id)
        self.assertNotEqual(self.fact(relationship=RelationshipKind.FEE_PAYER).fact_id,
                            self.fact(relationship=RelationshipKind.PROGRAM_INVOLVEMENT).fact_id)
        with self.assertRaises(ValueError):
            self.fact(signature="bad-signature")
        with self.assertRaises(ValueError):
            InstructionLocation(-1)

    def test_transaction_level_signer_and_fee_payer_can_overlap(self) -> None:
        signer = self.fact(relationship=RelationshipKind.SIGNER)
        payer = self.fact(relationship=RelationshipKind.FEE_PAYER)
        signer_evidence = self.evidence(
            "signer-evidence",
            evidence_type=EvidenceType.TRANSACTION_REFERENCE,
            activity_fact_id=signer.fact_id,
        )
        payer_evidence = self.evidence(
            "payer-evidence",
            evidence_type=EvidenceType.TRANSACTION_REFERENCE,
            activity_fact_id=payer.fact_id,
        )

        snapshot = build_snapshot(
            definition=self.definition,
            network=self.network,
            finalized_cutoff_slot=10,
            generated_at=STAMP,
            source_runs=(self.run_record(),),
            source_evidence=(signer_evidence, payer_evidence),
            activity_facts=(signer, payer),
        )

        self.assertEqual(
            {fact.relationship for fact in snapshot.activity_facts},
            {RelationshipKind.SIGNER, RelationshipKind.FEE_PAYER},
        )
        self.assertTrue(all(fact.instruction_location is None for fact in snapshot.activity_facts))

    def test_network_mismatch_and_unresolved_provenance_are_rejected(self) -> None:
        other_network = NetworkIdentity("devnet", "different-genesis")
        with self.assertRaises(ValueError):
            build_snapshot(definition=self.definition, network=self.network, finalized_cutoff_slot=10,
                           generated_at=STAMP, source_runs=(self.run_record(network=other_network),))
        with self.assertRaisesRegex(ValueError, "unknown source evidence"):
            build_snapshot(definition=self.definition, network=self.network, finalized_cutoff_slot=10,
                           generated_at=STAMP, candidates=(self.candidate(),))
        with self.assertRaisesRegex(ValueError, "unknown source run"):
            build_snapshot(definition=self.definition, network=self.network, finalized_cutoff_slot=10,
                           generated_at=STAMP, source_evidence=(self.evidence(),))

    def test_curated_evidence_requires_researcher_and_rationale(self) -> None:
        with self.assertRaises((TypeError, ValueError)):
            SourceEvidence("e", "r", EvidenceType.CURATED_SEED, "ref", STAMP, self.network)
        with self.assertRaises(ValueError):
            SourceEvidence("e", "r", EvidenceType.TRANSACTION_REFERENCE, "ref", STAMP,
                           self.network, researcher="unexpected")

    def test_run_window_and_required_identifiers_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            SourceRun("r", "s", "q", STAMP, self.network, window_start_slot=4)
        with self.assertRaises(ValueError):
            SourceRun("r", "s", "q", STAMP, self.network, window_start_slot=5, window_end_slot=4)

    def test_run_window_may_extend_past_cutoff_but_facts_may_not(self) -> None:
        run = replace(self.run_record(), window_start_slot=8, window_end_slot=12)
        fact_at_cutoff = self.fact(slot=10)
        evidence_at_cutoff = self.evidence(
            "activity-at-cutoff",
            evidence_type=EvidenceType.TRANSACTION_REFERENCE,
            activity_fact_id=fact_at_cutoff.fact_id,
        )

        snapshot = build_snapshot(
            definition=self.definition,
            network=self.network,
            finalized_cutoff_slot=10,
            generated_at=STAMP,
            source_runs=(run,),
            source_evidence=(evidence_at_cutoff,),
            activity_facts=(fact_at_cutoff,),
        )

        self.assertEqual(snapshot.source_runs[0].window_start_slot, 8)
        self.assertEqual(snapshot.source_runs[0].window_end_slot, 12)
        self.assertEqual(snapshot.activity_facts, (fact_at_cutoff,))

        fact_after_cutoff = self.fact(slot=11)
        evidence_after_cutoff = self.evidence(
            "activity-after-cutoff",
            evidence_type=EvidenceType.TRANSACTION_REFERENCE,
            activity_fact_id=fact_after_cutoff.fact_id,
        )
        with self.assertRaisesRegex(ValueError, "activity fact slot exceeds the finalized snapshot cutoff"):
            build_snapshot(
                definition=self.definition,
                network=self.network,
                finalized_cutoff_slot=10,
                generated_at=STAMP,
                source_runs=(run,),
                source_evidence=(evidence_after_cutoff,),
                activity_facts=(fact_after_cutoff,),
            )


class WalletDatasetSnapshotTests(unittest.TestCase):
    setUp = WalletDatasetContractTests.setUp
    run_record = WalletDatasetContractTests.run_record
    evidence = WalletDatasetContractTests.evidence
    candidate = WalletDatasetContractTests.candidate
    fact = WalletDatasetContractTests.fact

    def make_fact_bundle(self, *, extra_run: bool = False):
        fact = self.fact()
        run1 = self.run_record()
        run2 = self.run_record("second-run")
        evidence1 = self.evidence("activity-1", evidence_type=EvidenceType.TRANSACTION_REFERENCE,
                                  activity_fact_id=fact.fact_id)
        evidence2 = self.evidence("activity-2", "second-run", evidence_type=EvidenceType.TRANSACTION_REFERENCE,
                                  activity_fact_id=fact.fact_id)
        sources = (run1, run2) if extra_run else (run1,)
        evidences = (evidence1, evidence2) if extra_run else (evidence1,)
        candidate = self.candidate(activity_fact_refs=(fact.fact_id,), provenance_refs=(evidence1.evidence_id,))
        return sources, evidences, fact, candidate

    def build(self, **changes: object):
        values: dict[str, object] = {
            "definition": self.definition,
            "network": self.network,
            "finalized_cutoff_slot": 10,
            "generated_at": STAMP,
            "source_runs": (self.run_record(),),
            "source_evidence": (self.evidence(),),
            "candidates": (self.candidate(),),
        }
        if "source_runs" in changes and "source_evidence" not in changes:
            values["source_evidence"] = ()
        if "source_runs" in changes and "candidates" not in changes:
            values["candidates"] = ()
        values.update(changes)
        return build_snapshot(**values)  # type: ignore[arg-type]

    def test_empty_snapshot_is_supported_and_count_is_consistent(self) -> None:
        snapshot = self.build(source_runs=(), source_evidence=(), candidates=())
        self.assertEqual(snapshot.manifest.candidate_count, 0)
        self.assertEqual(snapshot.candidates, ())
        self.assertEqual(len(snapshot.manifest.content_digest), 64)

    def test_candidate_count_includes_excluded_decisions(self) -> None:
        excluded = self.candidate(address=OTHER_ADDRESS, decision=MembershipDecision.EXCLUDE,
                                  reason_code="review_excluded")
        snapshot = self.build(candidates=(self.candidate(), excluded))
        self.assertEqual(snapshot.manifest.candidate_count, 2)

    def test_exact_duplicate_candidates_are_idempotent_and_conflicts_rejected(self) -> None:
        snapshot = self.build(candidates=(self.candidate(), self.candidate()))
        self.assertEqual(len(snapshot.candidates), 1)
        with self.assertRaisesRegex(ValueError, "conflicting candidate membership"):
            self.build(candidates=(self.candidate(), self.candidate(decision=MembershipDecision.EXCLUDE)))

    def test_exact_duplicate_facts_are_idempotent_and_conflicts_rejected(self) -> None:
        runs, evidence, fact, candidate = self.make_fact_bundle()
        snap = self.build(source_runs=runs, source_evidence=evidence, activity_facts=(fact, fact),
                          candidates=(candidate,))
        self.assertEqual(len(snap.activity_facts), 1)
        with self.assertRaisesRegex(ValueError, "conflicting activity fact"):
            self.build(source_runs=runs, source_evidence=evidence,
                       activity_facts=(fact, self.fact(slot=9)), candidates=(candidate,))

    def test_same_normalized_fact_retains_evidence_from_multiple_runs(self) -> None:
        runs, evidence, fact, candidate = self.make_fact_bundle(extra_run=True)
        snapshot = self.build(source_runs=runs, source_evidence=evidence, activity_facts=(fact,),
                              candidates=(candidate,))
        self.assertEqual(len(snapshot.activity_facts), 1)
        self.assertEqual(len(snapshot.source_runs), 2)
        self.assertEqual(len(snapshot.source_evidence), 2)

    def test_duplicate_source_evidence_is_idempotent_but_conflicts_rejected(self) -> None:
        item = self.evidence()
        self.assertEqual(len(self.build(source_evidence=(item, item)).source_evidence), 1)
        conflict = SourceEvidence(item.evidence_id, item.source_run_id, item.evidence_type,
                                  "different-reference", item.captured_at, item.network,
                                  researcher=item.researcher, rationale=item.rationale)
        with self.assertRaisesRegex(ValueError, "conflicting source evidence"):
            self.build(source_evidence=(item, conflict))

    def test_candidate_and_evidence_references_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown activity fact"):
            self.build(candidates=(self.candidate(activity_fact_refs=("missing",)),))
        fact = self.fact()
        wrong = self.candidate(address=OTHER_ADDRESS, activity_fact_refs=(fact.fact_id,))
        evidence = self.evidence("activity", evidence_type=EvidenceType.TRANSACTION_REFERENCE,
                                 activity_fact_id=fact.fact_id)
        seed_evidence = self.evidence()
        with self.assertRaisesRegex(ValueError, "same network-scoped address"):
            self.build(source_evidence=(evidence, seed_evidence), activity_facts=(fact,), candidates=(wrong,))

    def test_activity_fact_requires_supporting_source_evidence(self) -> None:
        fact = self.fact()
        with self.assertRaisesRegex(ValueError, "at least one source evidence"):
            self.build(activity_facts=(fact,))

    def test_input_order_does_not_change_order_serialization_or_digest(self) -> None:
        excluded = self.candidate(address=OTHER_ADDRESS, decision=MembershipDecision.EXCLUDE,
                                  reason_code="review_excluded")
        first = self.build(candidates=(self.candidate(), excluded),
                           source_runs=(self.run_record(), self.run_record("second-run")),
                           source_evidence=(self.evidence(), self.evidence("seed-2")))
        second = self.build(candidates=(excluded, self.candidate()),
                            source_runs=(self.run_record("second-run"), self.run_record()),
                            source_evidence=(self.evidence("seed-2"), self.evidence()))
        self.assertEqual(first.candidates, second.candidates)
        self.assertEqual(first.source_runs, second.source_runs)
        self.assertEqual(serialize_snapshot_content(first), serialize_snapshot_content(second))
        self.assertEqual(first.manifest.content_digest, second.manifest.content_digest)

    def test_digest_is_stable_and_generated_at_is_excluded(self) -> None:
        earlier = self.build(generated_at=STAMP)
        later = self.build(generated_at=STAMP + timedelta(days=1))
        self.assertNotEqual(earlier.manifest.generated_at, later.manifest.generated_at)
        self.assertEqual(earlier.manifest.content_digest, later.manifest.content_digest)
        self.assertEqual(earlier.manifest.content_digest, self.build().manifest.content_digest)

    def test_definition_versions_and_network_identity_affect_digest(self) -> None:
        baseline = self.build()
        for definition in (
            DatasetDefinition("research-cohort", "1.0.1", "1.0.0", "1.0.0"),
            DatasetDefinition("research-cohort", "1.0.0", "1.0.1", "1.0.0"),
            DatasetDefinition("research-cohort", "1.0.0", "1.0.0", "1.0.1"),
        ):
            with self.subTest(definition=definition):
                self.assertNotEqual(baseline.manifest.content_digest,
                                    self.build(definition=definition).manifest.content_digest)
        other_network = NetworkIdentity("devnet", "genesis-b")
        self.assertNotEqual(baseline.manifest.content_digest,
                            self.build(network=other_network, source_runs=(self.run_record(network=other_network),),
                                       source_evidence=(self.evidence(network=other_network),),
                                       candidates=(self.candidate(network=other_network),)).manifest.content_digest)

    def test_digest_changes_with_cutoff_or_coverage_and_canonical_bytes_are_utf8(self) -> None:
        first = self.build()
        changed = self.build(finalized_cutoff_slot=11)
        self.assertNotEqual(first.manifest.content_digest, changed.manifest.content_digest)
        partial_run = replace(self.run_record(), coverage_status=CoverageStatus.PARTIAL)
        partial = self.build(source_runs=(partial_run,), coverage_status=CoverageStatus.PARTIAL)
        self.assertNotEqual(first.manifest.content_digest, partial.manifest.content_digest)
        self.assertIsInstance(serialize_snapshot_content(first), bytes)
        self.assertEqual(first.manifest.content_digest,
                         sha256(serialize_snapshot_content(first)).hexdigest())
        self.assertNotIn(b"generated_at", serialize_snapshot_content(first))

    def test_invalid_evidence_run_and_activity_network_references_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown source run"):
            self.build(source_evidence=(self.evidence(run_id="missing"),))
        fact = self.fact()
        other = NetworkIdentity("devnet", "other")
        evidence = self.evidence("activity", evidence_type=EvidenceType.TRANSACTION_REFERENCE,
                                 activity_fact_id=fact.fact_id, network=other)
        with self.assertRaisesRegex(ValueError, "network identity"):
            self.build(source_evidence=(evidence,), activity_facts=(fact,))

    def test_duplicate_source_runs_are_idempotent_and_conflicts_rejected(self) -> None:
        run = self.run_record()
        self.assertEqual(len(self.build(source_runs=(run, run)).source_runs), 1)
        conflicting = SourceRun(run.run_id, run.source_id, "different operation", run.acquired_at,
                                run.network, run.coverage_status)
        with self.assertRaisesRegex(ValueError, "conflicting source run"):
            self.build(source_runs=(run, conflicting))

    def test_provenance_does_not_require_or_serialize_endpoint_credentials(self) -> None:
        run = self.run_record()
        snapshot = self.build()
        encoded = serialize_snapshot_content(snapshot)
        self.assertFalse(hasattr(run, "endpoint"))
        self.assertNotIn(b"endpoint", encoded)
        self.assertNotIn(b"api_key", encoded)
        self.assertNotIn(b"authorization", encoded)

    def test_direct_snapshot_constructor_rejects_manifest_content_mismatch(self) -> None:
        snapshot = self.build()
        with self.assertRaisesRegex(ValueError, "candidate_count"):
            type(snapshot)(snapshot.manifest, (), snapshot.source_runs,
                           snapshot.source_evidence, snapshot.activity_facts)

    def empty_manifest(self, *, network: NetworkIdentity | None = None) -> SnapshotManifest:
        base = build_snapshot(
            definition=self.definition,
            network=network or self.network,
            finalized_cutoff_slot=10,
            generated_at=STAMP,
        )
        return base.manifest

    def construct_direct(self, manifest: SnapshotManifest, **records: object) -> DatasetSnapshot:
        values: dict[str, object] = {
            "candidates": (),
            "source_runs": (),
            "source_evidence": (),
            "activity_facts": (),
        }
        values.update(records)
        return DatasetSnapshot(manifest=manifest, **values)  # type: ignore[arg-type]

    def test_direct_snapshot_rejects_mutable_or_wrong_type_collections(self) -> None:
        manifest = self.empty_manifest()
        with self.assertRaisesRegex(TypeError, "must be a tuple"):
            self.construct_direct(manifest, candidates=[])
        with self.assertRaisesRegex(TypeError, "invalid record type"):
            self.construct_direct(manifest, source_runs=(object(),))

    def test_direct_snapshot_rejects_network_mismatches(self) -> None:
        manifest = self.empty_manifest()
        other = NetworkIdentity("devnet", "other-genesis")
        wrong_records = (
            {"candidates": (self.candidate(network=other),)},
            {"source_runs": (self.run_record(network=other),)},
            {"source_evidence": (self.evidence(network=other),)},
            {"activity_facts": (self.fact(network=other),)},
        )
        for records in wrong_records:
            with self.subTest(records=tuple(records)), self.assertRaisesRegex(
                ValueError, "network identity"
            ):
                self.construct_direct(manifest, **records)

    def test_direct_snapshot_rejects_unknown_graph_references(self) -> None:
        manifest = self.empty_manifest()
        cases = (
            ({"source_evidence": (self.evidence(),)}, "unknown source run"),
            ({"candidates": (self.candidate(),)}, "unknown source evidence"),
            ({"source_runs": (self.run_record(),),
              "source_evidence": (self.evidence(),),
              "candidates": (self.candidate(activity_fact_refs=("missing",)),)},
             "unknown activity fact"),
            ({"source_runs": (self.run_record(),),
              "source_evidence": (self.evidence(
                  evidence_type=EvidenceType.TRANSACTION_REFERENCE,
                  activity_fact_id="missing-fact",
              ),)},
             "unknown activity fact"),
        )
        for records, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.construct_direct(manifest, **records)

    def test_direct_snapshot_rejects_mismatched_candidate_fact_and_unsupported_facts(self) -> None:
        manifest = self.empty_manifest()
        fact = self.fact()
        evidence = self.evidence(
            "activity-evidence",
            evidence_type=EvidenceType.TRANSACTION_REFERENCE,
            activity_fact_id=fact.fact_id,
        )
        seed_evidence = self.evidence()
        wrong_candidate = self.candidate(
            address=OTHER_ADDRESS,
            provenance_refs=(seed_evidence.evidence_id,),
            activity_fact_refs=(fact.fact_id,),
        )
        with self.assertRaisesRegex(ValueError, "same network-scoped address"):
            self.construct_direct(
                manifest,
                source_runs=(self.run_record(),),
                source_evidence=(evidence, seed_evidence),
                candidates=(wrong_candidate,),
                activity_facts=(fact,),
            )
        with self.assertRaisesRegex(ValueError, "at least one source evidence"):
            self.construct_direct(manifest, activity_facts=(fact,))

    def test_direct_snapshot_rejects_activity_beyond_manifest_cutoff(self) -> None:
        manifest = self.empty_manifest()
        fact = self.fact(slot=11)
        evidence = self.evidence(
            "activity-evidence",
            evidence_type=EvidenceType.TRANSACTION_REFERENCE,
            activity_fact_id=fact.fact_id,
        )
        with self.assertRaisesRegex(ValueError, "exceeds the finalized snapshot cutoff"):
            self.construct_direct(
                manifest,
                source_runs=(self.run_record(),),
                source_evidence=(evidence,),
                activity_facts=(fact,),
            )

    def test_direct_snapshot_rejects_conflicting_duplicate_identity(self) -> None:
        manifest = self.empty_manifest()
        first, conflict = self.run_record(), replace(self.run_record(), operation="different")
        with self.assertRaisesRegex(ValueError, "conflicting source run"):
            self.construct_direct(manifest, source_runs=(first, conflict))

    def test_direct_snapshot_rejects_conflicting_candidate_evidence_and_fact_duplicates(self) -> None:
        manifest = self.empty_manifest()
        candidate = self.candidate()
        conflicting_candidate = replace(candidate, reason_code="other_reason")
        evidence = self.evidence()
        conflicting_evidence = replace(evidence, reference="different-reference")
        fact = self.fact()
        conflicting_fact = replace(fact, slot=fact.slot + 1)
        cases = (
            ({"candidates": (candidate, conflicting_candidate)}, "candidate membership"),
            ({"source_evidence": (evidence, conflicting_evidence)}, "source evidence"),
            ({"activity_facts": (fact, conflicting_fact)}, "activity fact"),
        )
        for records, label in cases:
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "conflicting"):
                self.construct_direct(manifest, **records)

    def test_direct_snapshot_rejects_inconsistent_source_run_references(self) -> None:
        manifest = self.empty_manifest()
        with self.assertRaisesRegex(ValueError, "source_run_refs"):
            self.construct_direct(manifest, source_runs=(self.run_record(),))

    def test_direct_snapshot_deduplicates_exact_records_and_rejects_bad_digest(self) -> None:
        run = self.run_record()
        valid = self.build(source_runs=(run,))
        deduplicated = DatasetSnapshot(
            valid.manifest,
            valid.candidates,
            (run, run),
            valid.source_evidence,
            valid.activity_facts,
        )
        self.assertEqual(deduplicated.source_runs, (run,))
        invalid_manifest = replace(valid.manifest, content_digest="0" * 64)
        with self.assertRaisesRegex(ValueError, "content_digest"):
            DatasetSnapshot(
                invalid_manifest,
                valid.candidates,
                valid.source_runs,
                valid.source_evidence,
                valid.activity_facts,
            )

    def test_builder_enforces_conservative_coverage_upper_bound(self) -> None:
        complete = replace(self.run_record(), coverage_status=CoverageStatus.COMPLETE)
        partial = replace(complete, run_id="partial-run", coverage_status=CoverageStatus.PARTIAL)
        unknown = replace(complete, run_id="unknown-run", coverage_status=CoverageStatus.UNKNOWN)
        scenarios = (
            ((complete,), (CoverageStatus.COMPLETE, CoverageStatus.PARTIAL, CoverageStatus.UNKNOWN)),
            ((complete, partial), (CoverageStatus.PARTIAL, CoverageStatus.UNKNOWN)),
            ((complete, unknown), (CoverageStatus.UNKNOWN,)),
            ((), (CoverageStatus.UNKNOWN,)),
        )
        for runs, allowed in scenarios:
            for status in CoverageStatus:
                with self.subTest(runs=tuple(run.coverage_status for run in runs), status=status):
                    if status in allowed:
                        snapshot = self.build(source_runs=runs, coverage_status=status)
                        self.assertEqual(snapshot.manifest.coverage_status, status)
                    else:
                        with self.assertRaisesRegex(ValueError, "coverage"):
                            self.build(source_runs=runs, coverage_status=status)

    def test_direct_snapshot_enforces_conservative_coverage_upper_bound(self) -> None:
        complete = replace(self.run_record(), coverage_status=CoverageStatus.COMPLETE)
        partial = replace(complete, run_id="partial-run", coverage_status=CoverageStatus.PARTIAL)
        unknown = replace(complete, run_id="unknown-run", coverage_status=CoverageStatus.UNKNOWN)
        cases = (
            ((complete,), CoverageStatus.COMPLETE,
             (CoverageStatus.COMPLETE, CoverageStatus.PARTIAL, CoverageStatus.UNKNOWN), None),
            ((complete, partial), CoverageStatus.PARTIAL,
             (CoverageStatus.PARTIAL, CoverageStatus.UNKNOWN), CoverageStatus.COMPLETE),
            ((complete, unknown), CoverageStatus.UNKNOWN,
             (CoverageStatus.UNKNOWN,), CoverageStatus.PARTIAL),
            ((), CoverageStatus.UNKNOWN, (CoverageStatus.UNKNOWN,), CoverageStatus.PARTIAL),
        )
        for runs, _supported, allowed, overstated in cases:
            for status in allowed:
                baseline = self.build(source_runs=runs, coverage_status=status)
                direct = self.construct_direct(baseline.manifest, source_runs=runs)
                self.assertEqual(direct.manifest.coverage_status, status)
            if overstated is not None:
                baseline = self.build(source_runs=runs, coverage_status=_supported)
                invalid_manifest = replace(baseline.manifest, coverage_status=overstated)
                with self.subTest(runs=tuple(run.coverage_status for run in runs),
                                  claim=overstated), self.assertRaisesRegex(ValueError, "coverage"):
                    self.construct_direct(invalid_manifest, source_runs=runs)


if __name__ == "__main__":
    unittest.main()
