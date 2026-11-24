"""按组签批判定：归属、守恒与闸门规则。"""
from hashlib import sha256

from app.intake.service import inspect
from app.modules.pipeline import run
from app.modules.signoff import build


def report(data):
    return run(data)


def test_every_input_line_has_one_unique_ledger_entry(dirty):
    signoff = report(dirty)["signoff"]
    ledger = signoff["ledger"]
    # 不丢记录：台账行数等于输入行数，条目号唯一
    assert len(ledger) == report(dirty)["intake"]["input"]
    assert len({e["entry_id"] for e in ledger}) == len(ledger)
    assert {e["line"] for e in ledger} == set(range(2, 2 + len(ledger)))
    # 每条未采信记录都带唯一处置和来源
    for entry in ledger:
        assert entry["source"] and entry["disposition"]
        if entry["disposition"] == "REJECTED":
            assert entry["reason"] and entry["attributable"] in (True, False)


def test_dirty_batch_gate_closes_for_unattributed_rows(dirty):
    gate = report(dirty)["signoff"]["gate"]
    assert not gate["open"]
    assert gate["reasons"] == ["UNATTRIBUTED_ISOLATION"]
    assert gate["unattributed"] == ["L17", "L18", "L19", "L20"]


def test_attributed_exception_only_blocks_its_own_group(attributable):
    signoff = report(attributable)["signoff"]
    assert signoff["gate"]["open"] and signoff["gate"]["reasons"] == []
    by_case = {g["case"]: g for g in signoff["groups"]}
    assert by_case["0001"]["eligible"] and by_case["0002"]["eligible"]
    blocked = by_case["0003"]
    assert not blocked["eligible"]
    assert "ATTRIBUTED_ISOLATION" in blocked["block_reasons"]
    # 异常去向可复核：隔离条目带行号、记录键、原因和落点
    assert {e["line"] for e in blocked["exceptions"]} == {12, 14}
    assert all(e["destination"] == "ISOLATED" for e in blocked["exceptions"])


def test_clean_groups_are_all_eligible(clean):
    groups = report(clean)["signoff"]["groups"]
    assert all(g["eligible"] for g in groups)
    assert all(not g["exceptions"] for g in groups)


def test_scope_pins_accepted_records_to_source_lines(attributable):
    group = next(
        g for g in report(attributable)["signoff"]["groups"] if g["case"] == "0001"
    )
    lines = [item["line"] for item in group["scope"]["records"]]
    assert lines == [2, 3, 4, 5]
    assert [item["record"] for item in group["scope"]["records"]] == [
        "000101",
        "000102",
        "000103",
        "000104",
    ]
    assert len({item["source"] for item in group["scope"]["records"]}) == 1


def test_ledger_mismatch_closes_gate_even_without_rejects():
    # 业务组采用记录数与采信数对不上：整批等待补齐。
    # 保留全部已知组以隔离“数量对不上”这一原因。
    intake = inspect(attributable_fixture())
    cases = [
        dict(case="0001", records=["000101"], status="READY"),
        dict(case="0002", records=[], status="READY"),
        dict(case="0003", records=[], status="EXPECTED_ONE_STAY"),
    ]
    signoff = build(intake, cases)
    assert not signoff["gate"]["open"]
    assert signoff["gate"]["reasons"] == ["LEDGER_MISMATCH"]


def test_empty_group_set_keeps_gate_closed():
    intake = inspect(attributable_fixture())
    signoff = build(intake, [])
    assert not signoff["gate"]["open"]
    assert "NO_BUSINESS_GROUP" in signoff["gate"]["reasons"]


def test_attribution_uses_known_cases_only(attributable):
    # 9999 不在业务组集合内时不可归属；同号进入组集合后即可归属
    intake = inspect(attributable_fixture())
    signoff = build(intake, [dict(case="0003", records=[], status="READY")])
    rejected = [e for e in signoff["ledger"] if e["disposition"] == "REJECTED"]
    assert all(e["attributable"] for e in rejected)


def test_ledger_entries_pin_source_fingerprint(dirty):
    digest = sha256(dirty).hexdigest()
    ledger = report(dirty)["signoff"]["ledger"]
    assert {entry["source"] for entry in ledger} == {digest}
    # 空白行与重复表头同样有唯一处置，不丢任何输入行
    dispositions = {entry["disposition"] for entry in ledger}
    assert {"ACCEPTED", "REJECTED", "BLANK_LINE", "HEADER_REPLAY"} <= dispositions


def attributable_fixture():
    from pathlib import Path

    return Path("sample_data/attributable.csv").read_bytes()
