import unittest
from dataclasses import replace
from qa.p4_research.n12_physical_destination import (
    PrivateHandlePath, Corroboration, assess_private_destination,
    observe_supplied_windows_handle,
)

FULL = Corroboration(True, True, True, True, True, True, True, True, True)
ROOT = PrivateHandlePath(r"\\?\C:\QA\UDF", 123, "permitted_root_handle")


def classify(path, *, request=None, root=ROOT, proofs=FULL, vol=123, origin="original_file_handle"):
    return assess_private_destination(
        write_target=PrivateHandlePath(path, vol, origin),
        allowed_roots=(root,), request_time_path=request or path,
        corroboration=proofs,
    )


class PhysicalDestinationCandidateTests(unittest.TestCase):
    def test_nested_permitted_path_is_only_a_candidate(self):
        r = classify(r"\\?\C:\QA\UDF\EBWebView\Network\0001.tmp")
        self.assertEqual(r.status, "CONTAINED_CANDIDATE_ONLY")
        self.assertEqual(r.public_receipt()["native_N12_acceptance"], "NOT_EVALUATED")

    def test_root_itself_is_not_a_universal_drive_allowance(self):
        r = classify(r"C:\outside\file.tmp", root=PrivateHandlePath("C:\\", 123, "permitted_root_handle"))
        self.assertEqual(r.status, "BLOCKED")

    def test_external_sibling_is_outside_candidate(self):
        self.assertEqual(classify(r"C:\QA\UDF-evil\file.tmp").status, "OUTSIDE_CANDIDATE_ONLY")

    def test_explicit_outside_is_outside_candidate(self):
        self.assertEqual(classify(r"C:\Windows\Temp\x.tmp").status, "OUTSIDE_CANDIDATE_ONLY")

    def test_case_mismatch_without_directory_case_evidence_blocks(self):
        # Even ASCII case changes can refer to a distinct case-sensitive
        # NTFS directory. Do not infer containment from path spelling alone.
        self.assertEqual(classify(r"c:\qa\udf\safe.tmp").status, "BLOCKED")

    def test_unicode_casefold_collision_never_grants_containment(self):
        # Python casefold equates 'Straße' and 'STRASSE', but that equivalence
        # is not proven for the actual Windows filesystem/volume.
        root = PrivateHandlePath(r"C:\QA\Straße", 123, "permitted_root_handle")
        r = classify(r"C:\QA\STRASSE\file.tmp", root=root)
        self.assertEqual(r.status, "BLOCKED")

    def test_exact_unicode_path_can_remain_a_candidate(self):
        root = PrivateHandlePath(r"C:\QA\Straße", 123, "permitted_root_handle")
        self.assertEqual(classify(r"C:\QA\Straße\file.tmp", root=root).status,
                         "CONTAINED_CANDIDATE_ONLY")

    def test_windows_invalid_name_characters_are_rejected(self):
        for character in '<>"|?*':
            with self.subTest(character=character):
                self.assertEqual(classify(r"C:\QA\UDF\bad" + character + "name.tmp").status, "BLOCKED")

    def test_reserved_dos_device_components_are_rejected(self):
        for component in ("NUL", "CON.txt", "AUX", "PRN", "COM1", "LPT9.log"):
            with self.subTest(component=component):
                self.assertEqual(classify("C:\\QA\\UDF\\" + component).status, "BLOCKED")

        self.assertEqual(classify(r"C:\QA\UDF\file.tmp", vol=44).status, "OUTSIDE_CANDIDATE_ONLY")

    def test_request_and_handle_mismatch_blocks(self):
        self.assertEqual(classify(r"C:\QA\UDF\file.tmp", request=r"C:\outside\file.tmp").status, "BLOCKED")

    def test_lexical_only_udf_not_handle_evidence(self):
        self.assertEqual(classify(r"C:\QA\UDF\file.tmp", origin="udf_lexical").status, "BLOCKED")

    def test_reopened_by_name_not_original(self):
        self.assertEqual(classify(r"C:\QA\UDF\file.tmp", origin="reopened_file").status, "BLOCKED")

    def test_root_without_handle_provenance_blocks(self):
        root = PrivateHandlePath(r"C:\QA\UDF", 123, "lexical_root")
        self.assertEqual(classify(r"C:\QA\UDF\file.tmp", root=root).status, "BLOCKED")

    def test_each_corroboration_gate_is_mandatory(self):
        for name in vars(FULL):
            with self.subTest(gate=name):
                self.assertEqual(classify(r"C:\QA\UDF\a", proofs=replace(FULL, **{name: False})).status, "BLOCKED")

    def test_truthy_strings_never_satisfy_evidence_gates(self):
        self.assertEqual(classify(r"C:\QA\UDF\file", proofs=replace(FULL, browser_identity_complete="yes")).status, "BLOCKED")

    def test_bare_unc_is_blocked(self):
        self.assertEqual(classify(r"\\server\share\QA\UDF\a").status, "BLOCKED")

    def test_extended_unc_is_blocked(self):
        self.assertEqual(classify(r"\\?\UNC\server\share\QA\UDF\a").status, "BLOCKED")

    def test_nt_device_alias_is_blocked(self):
        self.assertEqual(classify(r"\\.\C:\QA\UDF\a").status, "BLOCKED")

    def test_globalroot_alias_is_blocked(self):
        self.assertEqual(classify(r"\\?\GLOBALROOT\Device\HarddiskVolume1\QA\UDF\a").status, "BLOCKED")

    def test_volume_guid_alias_is_blocked(self):
        self.assertEqual(classify(r"\\?\Volume{1234}\QA\UDF\a").status, "BLOCKED")

    def test_parent_segment_is_blocked(self):
        self.assertEqual(classify(r"C:\QA\UDF\..\outside\a").status, "BLOCKED")

    def test_dot_segment_is_blocked(self):
        self.assertEqual(classify(r"C:\QA\UDF\.\a").status, "BLOCKED")

    def test_ads_stream_is_blocked(self):
        self.assertEqual(classify(r"C:\QA\UDF\file:stream").status, "BLOCKED")

    def test_double_separator_is_blocked(self):
        self.assertEqual(classify(r"C:\QA\UDF\\a").status, "BLOCKED")

    def test_control_character_is_blocked(self):
        self.assertEqual(classify("C:\\QA\\UDF\\bad\x00path").status, "BLOCKED")

    def test_trailing_dot_segment_is_blocked(self):
        self.assertEqual(classify(r"C:\QA\UDF\bad.\file").status, "BLOCKED")

    def test_drive_relative_is_blocked(self):
        self.assertEqual(classify(r"C:QA\UDF\file").status, "BLOCKED")

    def test_invalid_bool_volume_is_blocked(self):
        self.assertEqual(classify(r"C:\QA\UDF\file", vol=True).status, "BLOCKED")

    def test_public_receipt_does_not_expose_path(self):
        p = r"C:\QA\UDF\private-sensitive-name.tmp"
        r = classify(p)
        self.assertNotIn(p, repr(r))
        self.assertNotIn("private-sensitive-name", str(r.public_receipt()))


    def test_later_exact_root_is_not_shadowed_by_ambiguous_case_root(self):
        # Roots must be considered as a set, not by order. A safe exact root
        # must be checked even if another root has an ambiguous case alias.
        target = r"C:\QA\UDF\file.tmp"
        ambiguous = PrivateHandlePath(r"C:\qa\udf", 123, "permitted_root_handle")
        for roots in ((ambiguous, ROOT), (ROOT, ambiguous)):
            with self.subTest(order=roots):
                self.assertEqual(assess_private_destination(
                    write_target=PrivateHandlePath(target, 123, "original_file_handle"),
                    allowed_roots=roots, request_time_path=target, corroboration=FULL,
                ).status, "CONTAINED_CANDIDATE_ONLY")

    def test_permitted_root_order_does_not_change_exact_result(self):
        from itertools import permutations
        target = r"C:\QA\UDF\file.tmp"
        variants = (
            PrivateHandlePath(r"C:\QA\UDf", 123, "permitted_root_handle"),
            ROOT,
            PrivateHandlePath(r"C:\irrelevant", 123, "permitted_root_handle"),
        )
        for roots in permutations(variants):
            with self.subTest(roots=tuple(r.final_path for r in roots)):
                result = assess_private_destination(
                    write_target=PrivateHandlePath(target, 123, "original_file_handle"),
                    allowed_roots=roots, request_time_path=target, corroboration=FULL,
                )
                self.assertEqual(result.status, "CONTAINED_CANDIDATE_ONLY")
                self.assertEqual(result.public_receipt()["native_N12_acceptance"], "NOT_EVALUATED")

    def test_ambiguous_root_case_is_still_blocked_without_exact_root(self):
        target = r"C:\QA\UDF\file.tmp"
        mixed = PrivateHandlePath(r"C:\qa\udf", 123, "permitted_root_handle")
        self.assertEqual(assess_private_destination(
            write_target=PrivateHandlePath(target, 123, "original_file_handle"),
            allowed_roots=(mixed,), request_time_path=target, corroboration=FULL,
        ).status, "BLOCKED")

    def test_malformed_boundary_inputs_fail_closed_without_exceptions(self):
        valid = dict(
            write_target=PrivateHandlePath(r"C:\QA\UDF\file.tmp", 123, "original_file_handle"),
            allowed_roots=(ROOT,), request_time_path=r"C:\QA\UDF\file.tmp",
            corroboration=FULL,
        )
        bad = (
            {"write_target": None},
            {"write_target": {"path": "C:\\QA\\UDF"}},
            {"allowed_roots": None},
            {"allowed_roots": (None,)},
            {"allowed_roots": ("C:\\QA\\UDF",)},
            {"allowed_roots": "C:\\QA\\UDF"},
            {"allowed_roots": (ROOT, None)},
            {"corroboration": None},
            {"corroboration": {"complete": True}},
        )
        for change in bad:
            with self.subTest(change=repr(change)):
                result = assess_private_destination(**(valid | change))
                self.assertEqual(result.status, "BLOCKED")
                self.assertEqual(result.public_receipt()["file_mutation_acceptance"], "NOT_EVALUATED")

    def test_nonwindows_adapter_refuses_without_access(self):
        import os
        if os.name != "nt":
            with self.assertRaisesRegex(RuntimeError, "WINDOWS_ADAPTER_NOT_AVAILABLE"):
                observe_supplied_windows_handle(1)

    def test_empty_root_set_blocks(self):
        r = assess_private_destination(
            write_target=PrivateHandlePath(r"C:\QA\UDF\file", 123, "original_file_handle"),
            allowed_roots=(), request_time_path=r"C:\QA\UDF\file", corroboration=FULL)
        self.assertEqual(r.status, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
