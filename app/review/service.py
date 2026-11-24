from datetime import datetime, timezone
from hashlib import sha256
from time import monotonic

from app.business import DomainIssue
from app.config import RULE_VERSION
from app.modules.pipeline import run

GROUP_STATUSES = ("APPROVED", "HELD")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def execute(store, data):
    start = monotonic()
    fingerprint = sha256(data).hexdigest()
    run_id = sha256(f"{RULE_VERSION}:{fingerprint}".encode()).hexdigest()
    try:
        return store.load(run_id)
    except DomainIssue as error:
        if error.code != "RUN_NOT_FOUND":
            raise
    report = run(data)
    report["manifest"] = dict(
        sha256=fingerprint,
        version=RULE_VERSION,
        created=now(),
        duration_ms=round((monotonic() - start) * 1000, 3),
        bytes=len(data),
        run_id=run_id,
    )
    return store.register(run_id, report)


def review(store, run_id, values):
    if not isinstance(values, dict):
        raise DomainIssue("REVIEW_FIELDS")
    revision, status, note = (values.get(key) for key in ("revision", "status", "note"))
    if (
        type(revision) is not int
        or revision < 0
        or status not in ("APPROVED", "HELD")
        or not isinstance(note, str)
        or not (3 <= len(note.strip()) <= 200)
    ):
        raise DomainIssue("REVIEW_FIELDS")
    current = store.load(run_id)
    if revision != current["revision"]:
        raise DomainIssue("STALE_REVIEW")
    if current["status"] == "APPROVED":
        raise DomainIssue("RUN_FINALIZED")
    if status == "APPROVED" and not current["report"]["balance"]["releasable"]:
        raise DomainIssue("UNRESOLVED_ISSUES")
    return store.revise(run_id, revision, status, note.strip(), now())


def decide(store, run_id, values):
    """对单个业务组下达签发/暂缓裁定。

    同一幂等键重试直接返回首次裁定，不新增行、不推进修订号；校验失败一律不
    写入，调用方拿到的仍是旧版本。
    """
    if not isinstance(values, dict):
        raise DomainIssue("DECISION_FIELDS")
    case_id = values.get("case")
    status = values.get("status")
    note = values.get("note")
    key = values.get("idempotency_key")
    revision = values.get("revision")
    if (
        not isinstance(case_id, str)
        or not case_id
        or status not in GROUP_STATUSES
        or not isinstance(note, str)
        or not (3 <= len(note.strip()) <= 200)
        or not isinstance(key, str)
        or not (8 <= len(key) <= 64)
        or not all(ch.isalnum() or ch in "_-" for ch in key)
        or type(revision) is not int
        or revision < 0
    ):
        raise DomainIssue("DECISION_FIELDS")
    note = note.strip()
    current = store.load(run_id)
    if current["status"] == "APPROVED":
        raise DomainIssue("RUN_FINALIZED")

    # 幂等优先：同键重试原样返回首次裁定，修订号不变
    for item in current["group_decisions"]:
        if item["idempotency_key"] == key:
            return current

    if revision != current["revision"]:
        raise DomainIssue("STALE_REVIEW")
    signoff = current["report"].get("signoff")
    if not signoff or not signoff["gate"]["open"]:
        raise DomainIssue("BATCH_GATE_CLOSED")
    group = next((g for g in signoff["groups"] if g["case"] == case_id), None)
    if group is None:
        raise DomainIssue("GROUP_UNKNOWN")
    if any(d["case_id"] == case_id for d in current["group_decisions"]):
        raise DomainIssue("GROUP_FINALIZED")
    if status == "APPROVED" and not group["eligible"]:
        raise DomainIssue("GROUP_NOT_ELIGIBLE")

    stored = store.decide_group(
        run_id,
        case_id,
        status,
        note,
        key,
        now(),
        group["scope"],
        revision,
    )
    result = store.load(run_id)
    if stored is not None:  # 事务内发现同键并发首写，保持幂等语义
        return result
    return result
