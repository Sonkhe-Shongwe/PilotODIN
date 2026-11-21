import json

from qa.p4_research import n12_driver_exit_control as control


IMAGE = r"c:\private\cmd.exe"
BIRTH = {"kind": 1, "record": 11, "pid": 321, "guid": "private-id", "ticks": 10_000_000, "image": IMAGE}
EXIT = {**BIRTH, "kind": 5, "record": 12, "ticks": 9_930_000, "image": "private unknown image"}


def test_historical_pattern_requires_a_unique_bound_exit_and_exact_birth_image():
    witness = {"pid": BIRTH["pid"], "birth": 9_900_000}
    result = control.sysmon_case(witness, [BIRTH, EXIT], IMAGE)
    assert result["historical_pattern"] and result["exit_minus_birth_ticks"] == -70_000
    assert "private" not in json.dumps(result)
    for records, expected in (([BIRTH, {**EXIT, "guid": "wrong"}], IMAGE),
                              ([BIRTH, EXIT, EXIT], IMAGE), ([BIRTH, EXIT], r"c:\elsewhere\cmd.exe"),
                              ([BIRTH, {**EXIT, "image": IMAGE}], IMAGE)):
        assert control.sysmon_case(witness, records, expected)["historical_pattern"] is False


def test_descendant_summary_reports_only_fixed_labels_and_relative_time():
    assert control.descendant_summary([BIRTH, EXIT], set()) == [
        {"process_family": "cmd", "exit_minus_birth_ticks": -70_000,
         "exit_image_form": "relative-or-unrecognized", "count": 1},
    ]
    assert control.descendant_summary([BIRTH, EXIT], {321}) == []
