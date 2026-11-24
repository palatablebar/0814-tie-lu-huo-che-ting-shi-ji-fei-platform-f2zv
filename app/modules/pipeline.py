from app.business import DomainIssue
from app.intake.service import inspect
from app.modules.calculate import compute
from app.modules.grouping import case_groups
from app.modules.policy import policy
from app.modules.prepare import prepare
from app.modules.reconcile import balance
from app.modules.signoff import build as build_signoff


def evaluate(rows, stage):
    case = {
        "case": rows[0]["case"],
        "records": [r["record"] for r in rows],
        "status": "READY",
    }
    try:
        case["prep"], payload = prepare(rows)
        if stage >= 3:
            case["measure"] = compute(payload)
        if stage >= 4:
            case.update(policy(case["measure"]))
    except DomainIssue as error:
        case["status"] = error.code
    return case


def run(data, stage=5):
    intake = inspect(data)
    output = {"intake": {k: v for k, v in intake.items() if k != "rows"}}
    if stage == 1:
        # 采信阶段先落逐行台账；归属结论需等业务组生成，在 stage 5 补全
        output["signoff"] = {"ledger": intake["ledger"], "gate": None, "groups": []}
        return output
    cases = [evaluate(rows, stage) for _, rows in case_groups(intake["rows"])]
    output["cases"] = cases
    if stage >= 5:
        output["balance"] = balance(intake, cases)
        output["signoff"] = build_signoff(intake, cases)
    return output
