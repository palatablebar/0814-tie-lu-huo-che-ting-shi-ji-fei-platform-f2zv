"""按业务组签批判定。

输入为 intake 采信结果与管线算出的业务组结论，输出：

- ``ledger``：每个输入行恰好一条处置，隔离行标注是否能归属到已知业务组；
- ``gate``：批次级闸门，不可归属异常或数量对不上时整批等待补齐；
- ``groups``：逐组签批资格、采用记录范围与异常去向。

纯函数，不触碰数据库，便于独立测试守恒与归属规则。
"""

from app.intake.service import ACCEPTED, REJECTED


def build(intake, cases):
    known = {case["case"] for case in cases}
    by_case = {case["case"]: case for case in cases}
    ledger, unattributed, attributed_cases = [], [], set()
    for item in intake["ledger"]:
        entry = dict(item)
        if entry["disposition"] == REJECTED:
            if entry["case"] in known:
                entry["attributable"] = True
                entry["group"] = entry["case"]
                attributed_cases.add(entry["case"])
            else:
                entry["attributable"] = False
                entry["group"] = None
                unattributed.append(entry["entry_id"])
        else:
            entry["attributable"] = None
            entry["group"] = entry["case"]
        ledger.append(entry)

    groups = []
    for case in cases:
        code = case["case"]
        records = [
            dict(
                record=record_id,
                line=intake["accepted_lines"].get(record_id),
                source=intake["source_sha256"],
            )
            for record_id in case["records"]
        ]
        exceptions = [
            dict(
                entry_id=entry["entry_id"],
                line=entry["line"],
                record=entry["record"],
                reason=entry["reason"],
                destination="ISOLATED",
            )
            for entry in ledger
            if entry["disposition"] == REJECTED and entry.get("group") == code
        ]
        eligible = case["status"] == "READY" and not exceptions
        groups.append(
            dict(
                case=code,
                status=case["status"],
                eligible=eligible,
                block_reasons=_block_reasons(case, exceptions),
                scope=dict(
                    source_sha256=intake["source_sha256"],
                    record_count=len(records),
                    records=records,
                ),
                exceptions=exceptions,
            )
        )

    disposition_total = len(ledger)
    accepted_total = sum(1 for entry in ledger if entry["disposition"] == ACCEPTED)
    scoped_total = sum(len(group["scope"]["records"]) for group in groups)
    conserved = (
        disposition_total == intake["input"]
        and accepted_total == intake["accepted"]
        and scoped_total == intake["accepted"]
    )
    gate_open = conserved and not unattributed and bool(groups)
    return dict(
        ledger=ledger,
        gate=dict(
            open=gate_open,
            conserved=conserved,
            input_lines=intake["input"],
            ledger_lines=disposition_total,
            unattributed=unattributed,
            reasons=_gate_reasons(conserved, unattributed, groups),
        ),
        groups=groups,
    )


def _block_reasons(case, exceptions):
    reasons = []
    if exceptions:
        reasons.append("ATTRIBUTED_ISOLATION")
    if case["status"] != "READY":
        reasons.append(case["status"])
    return reasons


def _gate_reasons(conserved, unattributed, groups):
    reasons = []
    if not conserved:
        reasons.append("LEDGER_MISMATCH")
    if unattributed:
        reasons.append("UNATTRIBUTED_ISOLATION")
    if not groups:
        reasons.append("NO_BUSINESS_GROUP")
    return reasons
