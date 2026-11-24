"""按组签批裁定：幂等、乐观锁、闸门与失败回滚。"""
import pytest

from app.business import DomainIssue
from app.review.service import decide, execute


def payload(case, status="APPROVED", note="组内来源已复核", revision=0, key=None):
    return dict(
        case=case,
        status=status,
        note=note,
        revision=revision,
        idempotency_key=key or f"key-{case}-1",
    )


def test_eligible_group_can_be_approved_while_others_wait(store, attributable):
    run = execute(store, attributable)
    out = decide(store, run["id"], payload("0001"))
    assert out["revision"] == 1
    decision = next(d for d in out["group_decisions"] if d["case_id"] == "0001")
    assert decision["status"] == "APPROVED"
    # 采用的记录范围随裁定冻结
    assert [r["record"] for r in decision["scope"]["records"]] == [
        "000101",
        "000102",
        "000103",
        "000104",
    ]
    # 无争议第二组不受拖累，仍可按期签批
    second = decide(store, run["id"], payload("0002", revision=1, key="key-0002-1"))
    assert second["revision"] == 2
    assert {d["case_id"] for d in second["group_decisions"]} == {"0001", "0002"}


def test_retry_with_same_idempotency_key_adds_no_decision(store, attributable):
    run = execute(store, attributable)
    request = payload("0001")
    first = decide(store, run["id"], request)
    retry = decide(store, run["id"], {**request, "note": "重试改写意见"})
    assert retry["revision"] == first["revision"] == 1
    assert len(retry["group_decisions"]) == 1
    assert retry["group_decisions"][0]["note"] == "组内来源已复核"


def test_blocked_group_approval_rejected_without_revision_bump(store, attributable):
    run = execute(store, attributable)
    before = store.load(run["id"])
    with pytest.raises(DomainIssue, match="GROUP_NOT_ELIGIBLE"):
        decide(store, run["id"], payload("0003"))
    after = store.load(run["id"])
    assert after["revision"] == before["revision"] == 0
    assert after["group_decisions"] == []


def test_hold_is_allowed_on_eligible_group(store, attributable):
    run = execute(store, attributable)
    out = decide(store, run["id"], payload("0002", status="HELD", note="暂挂等待补充"))
    assert out["group_decisions"][0]["status"] == "HELD" and out["revision"] == 1


def test_gate_closed_blocks_every_group_decision(store, dirty):
    run = execute(store, dirty)
    with pytest.raises(DomainIssue, match="BATCH_GATE_CLOSED"):
        decide(store, run["id"], payload("0002"))  # 即使该组本身无争议
    assert store.load(run["id"])["revision"] == 0


def test_unknown_group_and_bad_fields(store, attributable):
    run = execute(store, attributable)
    with pytest.raises(DomainIssue, match="GROUP_UNKNOWN"):
        decide(store, run["id"], payload("7777"))
    bad = payload("0001")
    bad["idempotency_key"] = "short"
    with pytest.raises(DomainIssue, match="DECISION_FIELDS"):
        decide(store, run["id"], bad)
    bad = payload("0001", note="短")
    with pytest.raises(DomainIssue, match="DECISION_FIELDS"):
        decide(store, run["id"], bad)


def test_stale_revision_changes_nothing(store, attributable):
    run = execute(store, attributable)
    decide(store, run["id"], payload("0001"))
    with pytest.raises(DomainIssue, match="STALE_REVIEW"):
        decide(store, run["id"], payload("0002", revision=0, key="key-0002-stale"))
    loaded = store.load(run["id"])
    assert loaded["revision"] == 1 and len(loaded["group_decisions"]) == 1


def test_one_group_keeps_only_one_decision(store, attributable):
    run = execute(store, attributable)
    decide(store, run["id"], payload("0001"))
    with pytest.raises(DomainIssue, match="GROUP_FINALIZED"):
        decide(store, run["id"], payload("0001", revision=1, key="key-0001-again"))
    assert len(store.load(run["id"])["group_decisions"]) == 1


def test_finalized_batch_rejects_group_decisions(store, clean):
    run = execute(store, clean)
    from app.review.service import review

    review(
        store,
        run["id"],
        dict(revision=0, status="APPROVED", note="整批签发完成"),
    )
    with pytest.raises(DomainIssue, match="RUN_FINALIZED"):
        decide(store, run["id"], payload("0001", revision=1))


def test_parallel_decisions_have_one_winner_per_group(store, attributable):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    run = execute(store, attributable)
    barrier = Barrier(2)

    def attempt(item):
        index, key = item
        barrier.wait(3)
        try:
            return decide(
                store,
                run["id"],
                payload("0001", note=f"并发意见0{index}", revision=0, key=key),
            )["revision"]
        except DomainIssue as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [(1, "key-alpha"), (2, "key-beta")]))
    winner = [value for value in results if isinstance(value, int)]
    loser = [value for value in results if isinstance(value, str)]
    # 唯一赢家：只有一个事务提交，败者因乐观锁或组唯一约束落败
    assert winner == [1] and loser in [
        ["STALE_REVIEW"],
        ["GROUP_FINALIZED"],
    ]
    loaded = store.load(run["id"])
    assert loaded["revision"] == 1 and len(loaded["group_decisions"]) == 1
