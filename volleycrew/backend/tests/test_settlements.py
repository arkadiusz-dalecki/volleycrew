from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.api.settlement_schemas import ReportPayment
from tests.test_auth import PREFIX, login, mutate
from tests.test_auth import system as system
from tests.test_enrollment import as_player, declaration, own, propose, setup_group
from tests.test_meetings import calendar_system as calendar_system
from tests.test_room import change, confirm, draft, start


def price(admin, meeting, cost):
    starts = date.fromisoformat(meeting["source_date"])
    view = admin.get(PREFIX + f"/meetings/{meeting['id']}").json()
    response = mutate(
        admin,
        f"/admin/meetings/{meeting['id']}/reschedule",
        {
            "expected_version": view["version"],
            "local_date": starts.isoformat(),
            "local_time": "18:00",
            "duration_minutes": 120,
            "cost_grosz": cost,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["term_version"] == view["term_version"]


def current(member):
    response = member.get(PREFIX + "/me/settlements")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("amount", [10000, 10001])
def test_amount_age_and_payment_review(calendar_system, amount):
    device, clock, admin, organizer, _, _, meeting, ids = setup_group(calendar_system, 1)
    price(admin, meeting, amount)
    assert draft(admin, meeting).status_code == 200
    start(clock, meeting)
    confirm(admin, meeting)
    player = as_player(device, ids[0])
    assert current(player)["due"] == amount
    assert current(player)["reminder"] is (amount > 10000)
    clock.at += timedelta(days=30)
    player = as_player(device, ids[0])
    assert login(admin, organizer, "Admin-test-passphrase-123").status_code == 200
    assert current(player)["reminder"] is (amount > 10000)
    clock.at += timedelta(microseconds=1)
    assert current(player)["reminder"] is True
    body = {"id": str(uuid4()), "meeting_ids": [meeting["id"]], "amount": amount}
    assert mutate(player, "/me/settlements/payments", body).status_code == 204
    assert mutate(player, "/me/settlements/payments", body).status_code == 204
    assert current(player)["due"] == 0
    assert current(player)["pending"] == amount
    assert current(player)["reminder"] is False
    assert len(current(player)["reports"]) == 1
    path = f"/admin/settlements/payments/{body['id']}"
    assert mutate(player, path, {"status": "paid"}).status_code == 403
    assert mutate(admin, path, {"status": "rejected", "reason": " "}).status_code == 422
    assert mutate(admin, path, {"status": "rejected", "reason": "Brak wpłaty"}).status_code == 204
    assert current(player)["reminder"] is True


def test_correction_retries_and_carries_credit(calendar_system):
    device, clock, admin, _, _, _, meeting, ids = setup_group(calendar_system, 3)
    price(admin, meeting, 20000)
    assert draft(admin, meeting, [ids[2]]).status_code == 200
    start(clock, meeting)
    view = confirm(admin, meeting)
    payer = as_player(device, ids[0])
    payment = {"id": str(uuid4()), "meeting_ids": [meeting["id"]], "amount": 10000}
    assert (
        mutate(admin, f"/admin/settlements/players/{ids[0]}/payments", payment).status_code == 204
    )
    event = next(row["event_id"] for row in view["players"] if row["player"]["id"] == ids[2])
    body = {"event_id": event, "value": "present", "reason": "Gracz dotarł na salę"}
    key = uuid4()
    for _ in range(2):
        response = change(
            admin, meeting, "attendance/corrections", body, key=key, version=view["version"]
        )
        assert response.status_code == 200, response.text
    account = current(payer)
    assert account["due"] == 0
    assert account["credit"] in {3333, 3334}
    assert account["reports"][0]["amount"] == 10000
    assert current(as_player(device, ids[2]))["due"] in {6666, 6667}

    correction = {
        "cost_grosz": 30000,
        "reason": "Dopłata za salę",
        "expected_version": response.json()["version"],
    }
    path = f"/admin/meetings/{meeting['id']}/cost"
    preview = mutate(admin, path + "/preview", correction)
    assert {share["amount"] for share in preview.json()["shares"]} == {10000}
    cost_key = str(uuid4())
    for _ in range(2):
        result = mutate(admin, path, correction, "PUT", **{"Idempotency-Key": cost_key})
        assert result.status_code == 200, result.text
    assert current(payer)["credit"] == 0
    assert current(payer)["reports"][0]["amount"] == 10000


def test_cost_only_edit_preserves_active_seat_offer(calendar_system):
    device, _, admin, _, member, player, meeting, ids = setup_group(calendar_system)
    assert declaration(member, meeting).status_code == 200
    assert declaration(as_player(device, ids[0]), meeting, "not-going").status_code == 200
    offer = propose(admin, meeting, player["id"])
    price(admin, meeting, 20000)
    assert own(member, meeting)["offer"]["id"] == offer["id"]
    response = mutate(member, f"/offers/{offer['id']}/accept", {"term_version": 1})
    assert response.status_code == 200, response.text


def test_pay_all_accepts_more_than_one_hundred_charges():
    meetings = [uuid4() for _ in range(101)]
    report = ReportPayment(id=uuid4(), meeting_ids=meetings, amount=10100)
    assert report.meeting_ids == meetings
