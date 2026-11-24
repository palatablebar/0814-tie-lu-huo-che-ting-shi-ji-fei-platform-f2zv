import io


def decide(client, run_id, payload):
    return client.post(
        f"/api/runs/{run_id}/decisions", json=payload
    )


def start(client, sample):
    return client.post("/api/runs", data={"sample": sample}).json


def test_group_decision_http_flow_and_idempotent_retry(client):
    run = start(client, "attributable")
    payload = dict(
        case="0001",
        status="APPROVED",
        note="工作台组签发",
        revision=0,
        idempotency_key="http-key-0001",
    )
    response = decide(client, run["id"], payload)
    assert response.status_code == 200 and response.json["revision"] == 1
    retry = decide(client, run["id"], payload)
    assert retry.status_code == 200 and retry.json["revision"] == 1
    assert len(retry.json["group_decisions"]) == 1


def test_gate_closed_returns_409_and_writes_nothing(client):
    run = start(client, "dirty")
    response = decide(
        client,
        run["id"],
        dict(
            case="0002",
            status="APPROVED",
            note="试图签发无争议组",
            revision=0,
            idempotency_key="http-key-dirty",
        ),
    )
    assert response.status_code == 409 and response.json["code"] == "BATCH_GATE_CLOSED"
    loaded = client.get(f"/api/runs/{run['id']}").json
    assert loaded["revision"] == 0 and loaded["group_decisions"] == []


def test_ineligible_group_returns_409(client):
    run = start(client, "attributable")
    response = decide(
        client,
        run["id"],
        dict(
            case="0003",
            status="APPROVED",
            note="试图签发异常组",
            revision=0,
            idempotency_key="http-key-blocked",
        ),
    )
    assert response.status_code == 409
    assert response.json["code"] == "GROUP_NOT_ELIGIBLE"


def test_unknown_group_is_404(client):
    run = start(client, "attributable")
    response = decide(
        client,
        run["id"],
        dict(
            case="7777",
            status="HELD",
            note="查无此组",
            revision=0,
            idempotency_key="http-key-unknown",
        ),
    )
    assert response.status_code == 404 and response.json["code"] == "GROUP_UNKNOWN"


def test_evidence_contains_ledger_and_decisions(client):
    run = start(client, "attributable")
    decide(
        client,
        run["id"],
        dict(
            case="0001",
            status="APPROVED",
            note="证据联调",
            revision=0,
            idempotency_key="http-key-evidence",
        ),
    )
    packet = client.get(f"/api/runs/{run['id']}/evidence").json
    assert packet["schema"] == "review-evidence/2"
    assert packet["signoff"]["gate"]["open"] is True
    assert len(packet["signoff"]["ledger"]) == packet["signoff"]["gate"]["input_lines"]
    assert packet["group_decisions"][0]["case_id"] == "0001"


def test_decision_requires_json_fields(client):
    run = start(client, "clean")
    response = decide(client, run["id"], dict(case="0001"))
    assert response.status_code == 422 and response.json["code"] == "DECISION_FIELDS"
