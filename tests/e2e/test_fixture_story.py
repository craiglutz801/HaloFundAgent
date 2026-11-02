import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from halo.db.session import get_app_engine, get_migration_engine
from halo.main import create_app
from halo.services.reset import reset_fixtures
from halo.settings import get_settings


@pytest.fixture
def client():
    reset_fixtures(get_settings())
    with TestClient(create_app()) as test_client:
        yield test_client


def login(client: TestClient, name: str) -> str:
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    roster = client.get("/api/v1/auth/fixture-principals").json()["principals"]
    person = next(item for item in roster if item["display_name"] == name)
    response = client.post(
        "/api/v1/auth/fixture-login",
        json={"principal_id": person["id"]},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_partner_sees_two_decisions_and_atlas_blockers(client: TestClient):
    login(client, "Jordan Hale")
    overview = client.get("/api/v1/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert {item["company_name"] for item in body["decisions"]} == {"Vela", "Rally"}
    questions = {item["question"] for item in body["blockers"]}
    assert questions == {"Reconcile retention definitions", "Obtain customer concentration evidence"}
    court = next(item for item in body["portfolio_attention"] if item["company_name"] == "Court")
    assert court["health"] == "unknown"


def test_analyst_cannot_see_atlas_by_list_direct_or_search(client: TestClient):
    login(client, "Jordan Hale")
    atlas = next(item for item in client.get("/api/v1/companies").json()["items"] if item["display_name"] == "Atlas")
    evidence = client.get(f"/api/v1/companies/{atlas['id']}").json()["evidence"][0]["id"]
    login(client, "Blake Iverson")
    listed = [item["display_name"] for item in client.get("/api/v1/companies").json()["items"]]
    assert listed == ["Vela"]
    hidden = client.get(f"/api/v1/companies/{atlas['id']}")
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "NOT_FOUND"
    assert client.get(f"/api/v1/evidence/{evidence}").status_code == 404
    assert client.get("/api/v1/evidence", params={"q": "retention"}).json()["items"] == []
    spoofed = client.get("/api/v1/companies", headers={"x-principal-id": atlas["id"]})
    assert [item["display_name"] for item in spoofed.json()["items"]] == ["Vela"]


def test_atlas_submission_reports_the_blockers(client: TestClient):
    csrf = login(client, "Priya Shah")
    atlas = next(item for item in client.get("/api/v1/companies").json()["items"] if item["display_name"] == "Atlas")
    detail = client.get(f"/api/v1/companies/{atlas['id']}").json()
    lenses = next(item["content"]["lenses"] for item in detail["artifacts"] if item["kind"] == "xavier_scorecard")
    assert [(item["lens"], item["score"]) for item in lenses] == [
        ("CX", 3),
        ("EX", None),
        ("BX", None),
        ("PX", 3),
    ]
    case = next(item for item in detail["cases"] if item["case_type"] == "initial")
    response = client.post(
        f"/api/v1/cases/{case['id']}/stage-actions",
        json={
            "action": "submit_ic",
            "rationale": "Attempt to submit Atlas before the open blockers are resolved.",
            "expected_case_version": case["row_version"],
        },
        headers={"x-csrf-token": csrf, "idempotency-key": str(uuid.uuid4())},
    )
    assert response.status_code == 409
    labels = [item["label"] for item in response.json()["details"]["missing_requirements"]]
    assert "Reconcile retention definitions" in labels
    assert "Obtain customer concentration evidence" in labels
    still = client.get(f"/api/v1/companies/{atlas['id']}").json()
    assert still["company"]["stage"] == "diligence"
    assert all(item["blocking"] for item in still["concerns"])


def test_review_does_not_clear_a_blocker(client: TestClient):
    csrf = login(client, "Priya Shah")
    atlas = next(item for item in client.get("/api/v1/companies").json()["items"] if item["display_name"] == "Atlas")
    detail = client.get(f"/api/v1/companies/{atlas['id']}").json()
    artifact = next(item for item in detail["artifacts"] if item["kind"] == "ainge_report")
    reviewed = client.post(
        f"/api/v1/artifacts/{artifact['id']}/reviews",
        json={
            "artifact_sha256": artifact["sha256"],
            "verdict": "approve_draft",
            "notes": "Reviewed the retention conflict. This note does not resolve it.",
        },
        headers={"x-csrf-token": csrf, "idempotency-key": str(uuid.uuid4())},
    )
    assert reviewed.status_code == 200
    concerns = client.get(f"/api/v1/companies/{atlas['id']}").json()["concerns"]
    assert {item["status"] for item in concerns} == {"open"}


def test_text_alone_cannot_resolve_a_concern(client: TestClient):
    csrf = login(client, "Priya Shah")
    atlas = next(item for item in client.get("/api/v1/companies").json()["items"] if item["display_name"] == "Atlas")
    concern = client.get(f"/api/v1/companies/{atlas['id']}").json()["concerns"][0]
    response = client.post(
        f"/api/v1/concerns/{concern['id']}/dispositions",
        json={
            "disposition": "resolved",
            "rationale": "Please treat this paragraph as enough.",
            "evidence_ids": [],
            "expected_version": concern["row_version"],
        },
        headers={"x-csrf-token": csrf, "idempotency-key": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "EVIDENCE_REQUIRED"


def test_vela_approval_is_closing_not_owned_and_replay_is_stable(client: TestClient):
    csrf = login(client, "Jordan Hale")
    before = {item["display_name"] for item in client.get("/api/v1/companies").json()["items"] if item["stage"] == "owned"}
    decision = next(item for item in client.get("/api/v1/overview").json()["decisions"] if item["company_name"] == "Vela")
    packet = client.get(f"/api/v1/ic-packets/{decision['packet_id']}").json()
    dissent = next(item for item in packet["artifacts"] if item["kind"] == "independent_risk_report")
    assert dissent["sealed_at"]
    body = {
        "packet_sha256": packet["manifest_sha256"],
        "decision": "approve",
        "rationale": "Approve Vela into closing. Ownership still needs a verified close.",
        "expected_case_version": packet["case"]["row_version"],
        "policy_version": packet["policy_version"],
    }
    key = str(uuid.uuid4())
    first = client.post(
        f"/api/v1/ic-packets/{packet['id']}/decisions",
        json=body,
        headers={"x-csrf-token": csrf, "idempotency-key": key},
    )
    assert first.status_code == 200
    assert first.json()["company_stage"] == "closing"
    assert first.json()["owned"] is False
    replay = client.post(
        f"/api/v1/ic-packets/{packet['id']}/decisions",
        json=body,
        headers={"x-csrf-token": csrf, "idempotency-key": key},
    )
    assert replay.status_code == 200
    assert replay.json()["decision_id"] == first.json()["decision_id"]
    conflict = client.post(
        f"/api/v1/ic-packets/{packet['id']}/decisions",
        json={**body, "rationale": "A different rationale must not reuse the key."},
        headers={"x-csrf-token": csrf, "idempotency-key": key},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    stale = client.post(
        f"/api/v1/ic-packets/{packet['id']}/decisions",
        json={
            **body,
            "packet_sha256": "0" * 64,
            "expected_case_version": first.json()["case_version"],
        },
        headers={"x-csrf-token": csrf, "idempotency-key": str(uuid.uuid4())},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_PACKET"
    owned = {item["display_name"] for item in client.get("/api/v1/companies").json()["items"] if item["stage"] == "owned"}
    assert owned == before
    saved = client.get(f"/api/v1/ic-packets/{packet['id']}").json()
    assert any(item["kind"] == "independent_risk_report" and item["sealed_at"] for item in saved["artifacts"])


def test_follow_on_approval_does_not_move_ownership_backward(client: TestClient):
    csrf = login(client, "Jordan Hale")
    rally = next(item for item in client.get("/api/v1/overview").json()["decisions"] if item["company_name"] == "Rally")
    packet = client.get(f"/api/v1/ic-packets/{rally['packet_id']}").json()
    response = client.post(
        f"/api/v1/ic-packets/{packet['id']}/decisions",
        json={
            "packet_sha256": packet["manifest_sha256"],
            "decision": "approve",
            "rationale": "Approve the follow-on case without changing Rally's ownership.",
            "expected_case_version": packet["case"]["row_version"],
            "policy_version": packet["policy_version"],
        },
        headers={"x-csrf-token": csrf, "idempotency-key": str(uuid.uuid4())},
    )
    assert response.status_code == 200
    assert response.json()["company_stage"] == "owned"
    assert response.json()["case_status"] == "closing"


def test_admin_cannot_decide_and_value_is_not_summed(client: TestClient):
    login(client, "Avery Brooks")
    assert client.get("/api/v1/administration").status_code == 200
    assert client.get("/api/v1/overview").json()["decisions"] == []
    csrf = login(client, "Jordan Hale")
    rally = next(item for item in client.get("/api/v1/overview").json()["decisions"] if item["company_name"] == "Rally")
    packet = client.get(f"/api/v1/ic-packets/{rally['packet_id']}").json()
    admin = login(client, "Avery Brooks")
    denied = client.post(
        f"/api/v1/ic-packets/{packet['id']}/decisions",
        json={
            "packet_sha256": packet["manifest_sha256"],
            "decision": "approve",
            "rationale": "An administrator must not be able to approve this packet.",
            "expected_case_version": packet["case"]["row_version"],
            "policy_version": packet["policy_version"],
        },
        headers={"x-csrf-token": admin, "idempotency-key": str(uuid.uuid4())},
    )
    assert denied.status_code == 403
    login(client, "Riley Quinn")
    ledger = client.get("/api/v1/value").json()
    assert ledger["total"] is None
    metrics = {item["metric"]: item for item in ledger["entries"]}
    assert metrics["tagged_meetings"]["classification"] == "observed"
    assert metrics["capacity_released"]["amount"] == "200.0000"
    assert metrics["capacity_released"]["classification"] == "estimated"
    assert {item["metric"] for item in ledger["gaps"]} == {"incremental_revenue", "cash_savings"}
    portfolio = client.get("/api/v1/portfolio").json()["companies"]
    assert next(item for item in portfolio if item["display_name"] == "Court")["health"] == "unknown"
    assert next(item for item in portfolio if item["display_name"] == "Rally")["health"] == "on_plan"
    assert client.get("/api/v1/overview").json()["notifications"] == []
    login(client, "Sam Okonkwo")
    notes = client.get("/api/v1/overview").json()["notifications"]
    assert len(notes) == 1
    assert "unknown" in notes[0]["body"]
    # The same event is not duplicated for this recipient.
    assert len({item["id"] for item in notes}) == 1
    # csrf is unused when the last call is a read; keep the login token referenced.
    assert csrf


def test_direct_stage_update_is_rejected_and_session_guc_does_not_leak():
    reset_fixtures(get_settings())
    engine = get_app_engine()
    with engine.connect() as connection:
        transaction = connection.begin()
        principal = connection.execute(
            text("SELECT id FROM halo_fixture_roster() WHERE display_name = 'Jordan Hale'")
        ).scalar()
        connection.execute(
            text("SELECT set_config('halo.principal_id', :principal, true)"),
            {"principal": str(principal)},
        )
        with pytest.raises(Exception, match="direct stage update rejected"):
            connection.execute(text("UPDATE companies SET stage = 'owned'"))
        transaction.rollback()
        transaction = connection.begin()
        leaked = connection.execute(text("SELECT current_setting('halo.principal_id', true)")).scalar()
        transaction.rollback()
    assert leaked in (None, "")


def test_reset_refuses_a_live_organization_inside_the_fixture_database():
    reset_fixtures(get_settings())
    engine = get_migration_engine()
    with engine.begin() as connection:
        connection.execute(text("UPDATE organizations SET mode = 'live'"))
    try:
        with pytest.raises(RuntimeError, match="non-fixture"):
            reset_fixtures(get_settings())
    finally:
        with engine.begin() as connection:
            connection.execute(text("UPDATE organizations SET mode = 'fixture'"))
