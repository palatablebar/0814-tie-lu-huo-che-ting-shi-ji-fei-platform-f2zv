import json


def artifact(run):
    report = run["report"]
    packet = {
        "schema": "review-evidence/2",
        "manifest": report["manifest"],
        "balance": report["balance"],
        "cases": report["cases"],
        "intake": report["intake"],
        "signoff": report.get("signoff"),
        "group_decisions": run.get("group_decisions", []),
        "review": {key: run[key] for key in ("status", "revision", "note", "reviewed")},
    }
    return (
        json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
