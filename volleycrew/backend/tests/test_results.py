from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.domain.rating import BASE_RATING, evaluate
from app.domain.replay import Match, replay
from tests.test_auth import PREFIX, mutate
from tests.test_auth import system as system
from tests.test_enrollment import as_player, setup_group
from tests.test_meetings import calendar_system as calendar_system
from tests.test_room import change, confirm, draft, start
from tests.test_schedule_changes import fresh


def prepare(system, count=4):
    group = setup_group(system, count)
    _, clock, admin, _, _, _, meeting, _ = group
    start(clock, meeting)
    assert draft(admin, meeting).status_code == 200
    confirm(admin, meeting)
    assert change(admin, meeting, "teams/generate", {"mode": "balanced"}).status_code == 200
    assert change(admin, meeting, "teams/confirm").status_code == 200
    return group


def preview(admin, meeting, sets_a=5, sets_b=3, correction=None):
    body = {
        "expected_version": fresh(admin, meeting)["version"],
        "sets_a": sets_a,
        "sets_b": sets_b,
        **(correction or {}),
    }
    response = mutate(
        admin,
        f"/admin/meetings/{meeting['id']}/result-correction-preview"
        if correction
        else f"/admin/meetings/{meeting['id']}/result-preview",
        body,
    )
    assert response.status_code == 200, response.text
    return body, response.json()


def save(admin, meeting, sets_a=5, sets_b=3, correction=None, key=None):
    body, view = preview(admin, meeting, sets_a, sets_b, correction)
    body["expected_rating_version"] = view["rating_version"]
    response = mutate(
        admin,
        f"/admin/meetings/{meeting['id']}/result/corrections"
        if correction
        else f"/admin/meetings/{meeting['id']}/result",
        body,
        **{"Idempotency-Key": str(key or uuid4())},
    )
    assert response.status_code == 200, response.text
    return response.json(), body


def result(client, meeting):
    response = client.get(PREFIX + f"/meetings/{meeting['id']}/result")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    "sets_a,sets_b,delta", [(5, 0, "16"), (3, 2, "3.2"), (6, 4, "3.2"), (3, 3, "0"), (0, 0, "0")]
)
def test_rating_examples(sets_a, sets_b, delta):
    value = evaluate(BASE_RATING, BASE_RATING, sets_a, sets_b)
    assert value.delta_a == Decimal(delta) and value.delta_b == -value.delta_a
    assert (value.share_a is None) == (sets_a + sets_b == 0)


def test_unequal_strength_and_invalid_inputs():
    assert evaluate(Decimal(1000), Decimal(1200), 3, 3).delta_a > 0
    assert evaluate(Decimal(1200), Decimal(1000), 3, 2).delta_a < 0
    assert (
        evaluate(Decimal(1000), Decimal(1200), 5, 0).delta_a
        > evaluate(Decimal(1000), Decimal(1200), 3, 2).delta_a
    )
    for a, b in [(-1, 0), (True, 3), (3.5, 2)]:
        with pytest.raises(ValueError):
            evaluate(BASE_RATING, BASE_RATING, a, b)


def test_pure_replay_is_stable_chronological_and_zero_sets_skip_entries():
    a, b, c = UUID(int=1), UUID(int=2), UUID(int=3)
    at = datetime(2026, 11, 10, tzinfo=UTC)
    first = Match(UUID(int=10), uuid4(), at, (a,), (b,), 5, 0)
    second = Match(UUID(int=20), uuid4(), at, (b,), (c,), 3, 2)
    zero = Match(UUID(int=30), uuid4(), at + timedelta(days=7), (a,), (c,), 0, 0)
    expected = replay([first, second, zero])
    assert replay([zero, second, first]) == expected
    assert len(expected[2]) == 4 and expected[1] == {a: 1, b: 2, c: 1}
    assert expected[3][1].before[b] == Decimal(984)
    assert sum(e.player_id == b for e in expected[2]) == 2
    corrected = Match(
        first.meeting_id, first.result_id, first.starts_at, first.team_a, first.team_b, 0, 5
    )
    assert replay([corrected, second])[0] != expected[0]
    assert replay([second, corrected])[0] == replay([corrected, second])[0]


def test_save_retry_zero_sets_and_private_correction(calendar_system):
    device, _, admin, _, member, _, meeting, ids = prepare(calendar_system)
    key = uuid4()
    view, body = save(admin, meeting, 5, 3, key=key)
    assert view["state"] == "played" and len(view["players"]) == 4
    assert {Decimal(p["delta"]) for p in view["players"]} == {Decimal(4), Decimal(-4)}
    repeated = mutate(
        admin, f"/admin/meetings/{meeting['id']}/result", body, **{"Idempotency-Key": str(key)}
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == view
    assert result(member, meeting)["revision"] == 1
    assert "reasons" not in result(member, meeting)
    teams = member.get(PREFIX + f"/meetings/{meeting['id']}/teams").json()
    correction = {
        "team_a": [p["player"]["id"] for p in teams["team_a"]],
        "team_b": [p["player"]["id"] for p in teams["team_b"]],
        "reason": "Błąd w zapisanych setach",
    }
    changed, _ = save(admin, meeting, 0, 0, correction)
    assert changed["state"] == "no_sets" and changed["players"] == []
    assert changed["reasons"]["2"] == correction["reason"]
    assert len(changed["revisions"]) == 2
    public = result(member, meeting)
    assert "Błąd" not in str(public) and "reasons" not in public
    ranking = member.get(PREFIX + "/ranking").json()
    assert all(Decimal(p["points"]) == BASE_RATING for p in ranking["items"])
    assert all(p["meetings"] == 0 for p in ranking["items"])
    assert (
        as_player(device, ids[0])
        .get(PREFIX + f"/admin/meetings/{meeting['id']}/result")
        .status_code
        == 403
    )
    assert fresh(admin, meeting)["participant_count"] == 4


def test_full_correction_updates_presence_pdf_teams_and_rating_privately(calendar_system):
    device, _, admin, _, member, _, meeting, ids = prepare(calendar_system)
    initial, _ = save(admin, meeting)
    teams = member.get(PREFIX + f"/meetings/{meeting['id']}/teams").json()
    a = [p["player"]["id"] for p in teams["team_a"]]
    b = [p["player"]["id"] for p in teams["team_b"]]
    removed = a[0]
    added = ids[4]
    a[0] = added
    correction = {
        "team_a": a,
        "team_b": b,
        "reason": "Poprawiony skład",
        "presence_changes": [
            {"player_id": removed, "value": "excused", "reason": "Prywatny powód nieobecności"},
            {"player_id": added, "value": "present", "reason": "Brakowało wpisu obecności"},
        ],
    }
    changed, _ = save(admin, meeting, 3, 2, correction)
    assert changed["revision"] == 2
    assert removed in {p["id"] for p in changed["squads"]["1"]["team_a"]}
    assert added in {p["id"] for p in changed["squads"]["2"]["team_a"]}
    assert {p["player"]["id"] for p in changed["players"]} == set(a + b)
    assert removed not in str(changed["players"])
    assert "Prywatny" not in str(result(member, meeting))
    history = as_player(device, removed).get(PREFIX + "/me/attendance-history").json()["items"][0]
    assert (
        history["current_kind"] == "excused"
        and history["corrections"][-1]["reason"] == "Prywatny powód nieobecności"
    )
    new_history = as_player(device, added).get(PREFIX + "/me/attendance-history").json()["items"][0]
    assert new_history["source_reason"] == "Brakowało wpisu obecności"
    assert new_history["current_kind"] == "present"
    current_teams = member.get(PREFIX + f"/meetings/{meeting['id']}/teams").json()
    assert {p["player"]["id"] for p in current_teams["team_a"]} == set(a)
    assert {p["id"] for p in fresh(member, meeting)["participants"]} == set(a + b)
    assert member.get(PREFIX + f"/players/{removed}/rating-history").json()["total"] == 0
    assert member.get(PREFIX + f"/players/{added}/rating-history").json()["total"] == 1
    assert admin.get(PREFIX + f"/admin/meetings/{meeting['id']}/signature-list").status_code == 200


def second_match(admin, clock, ids, a, b, manual=True):
    from app.models.auth import Player
    from app.services.enrollment import declare
    from tests.test_meetings import resolve_day

    meeting = resolve_day(admin, "2026-11-17")

    async def enroll():
        async with admin.app.state.database.sessions() as db:
            for identifier in ids:
                await declare(
                    db,
                    UUID(meeting["id"]),
                    await db.get(Player, UUID(identifier)),
                    "going",
                    1,
                    clock.now(),
                    uuid4(),
                )
            await db.commit()

    admin.portal.call(enroll)
    start(clock, meeting)
    assert draft(admin, meeting).status_code == 200
    confirm(admin, meeting)
    assert (
        change(
            admin, meeting, "teams/generate", {"mode": "random" if manual else "balanced"}
        ).status_code
        == 200
    )
    if manual:
        assert change(admin, meeting, "teams", {"team_a": a, "team_b": b}, "PUT").status_code == 200
    assert change(admin, meeting, "teams/confirm").status_code == 200
    return meeting


def team_ids(client, meeting):
    teams = client.get(PREFIX + f"/meetings/{meeting['id']}/teams").json()
    return [p["player"]["id"] for p in teams["team_a"]], [
        p["player"]["id"] for p in teams["team_b"]
    ]


def test_older_result_and_correction_replay_later_matches_exactly(calendar_system):
    _, clock, admin, _, member, _, first, ids = prepare(calendar_system)
    a, b = team_ids(member, first)
    second = second_match(admin, clock, ids[:4], a, b)
    later_before, _ = save(admin, second, 3, 2)
    assert Decimal(later_before["outcome"]["mean_a"]) == 1000
    first_result, _ = save(admin, first, 5, 0)
    later = result(member, second)
    assert Decimal(later["outcome"]["mean_a"]) == 1016
    assert Decimal(later["outcome"]["mean_b"]) == 984
    assert (
        Decimal(later["outcome"]["delta_a"]) == evaluate(Decimal(1016), Decimal(984), 3, 2).delta_a
    )
    corrected, _ = save(
        admin, first, 0, 5, {"team_a": a, "team_b": b, "reason": "Odwrotnie zapisane sety"}
    )
    assert corrected["revision"] == 2
    later = result(member, second)
    expected = evaluate(Decimal(984), Decimal(1016), 3, 2).delta_a
    assert Decimal(later["outcome"]["delta_a"]) == expected
    assert Decimal(later["players"][0]["before"]) in {Decimal(984), Decimal(1016)}
    ratings = member.get(PREFIX + "/ranking?limit=100").json()
    from app.domain.rating import apply_delta

    actual = {row["player"]["id"]: Decimal(row["points"]) for row in ratings["items"]}
    assert all(actual[p] == apply_delta(Decimal(984), expected) for p in a)
    assert all(actual[p] == apply_delta(Decimal(1016), expected.copy_negate()) for p in b)
    # Repeating a deterministic full replay does not accumulate rounding or double-count.
    from app.services.results import matches, persist_replay, state_lock

    async def repeat():
        async with admin.app.state.database.sessions() as db:
            state = await state_lock(db, write=True)
            await persist_replay(db, replay(await matches(db)), state)
            await db.commit()

    admin.portal.call(repeat)
    assert {
        r["player"]["id"]: Decimal(r["points"])
        for r in member.get(PREFIX + "/ranking?limit=100").json()["items"]
    } == actual
    assert first_result["revision"] == 1


def test_stale_preview_permissions_and_mid_write_failure_roll_back(calendar_system, monkeypatch):
    from app.services import results as service

    _, _, admin, _, member, _, meeting, _ = prepare(calendar_system)
    body, view = preview(admin, meeting)
    body["expected_rating_version"] = view["rating_version"]
    key = uuid4()
    path = f"/admin/meetings/{meeting['id']}/result"
    assert mutate(member, path, body, **{"Idempotency-Key": str(key)}).status_code == 403
    assert (
        mutate(
            member,
            f"/admin/meetings/{meeting['id']}/result-preview",
            {k: v for k, v in body.items() if k != "expected_rating_version"},
        ).status_code
        == 403
    )
    original = service.persist_replay

    async def fail(db, calculation, state):
        await original(db, calculation, state)
        raise RuntimeError("Injected transaction failure after rating write")

    monkeypatch.setattr(service, "persist_replay", fail)
    with pytest.raises(RuntimeError, match="Injected transaction failure"):
        mutate(admin, path, body, **{"Idempotency-Key": str(key)})
    assert result(member, meeting) is None
    assert fresh(admin, meeting)["status"] == "teams_confirmed"
    assert all(
        Decimal(row["points"]) == 1000 for row in member.get(PREFIX + "/ranking").json()["items"]
    )
    monkeypatch.setattr(service, "persist_replay", original)
    saved = mutate(admin, path, body, **{"Idempotency-Key": str(key)})
    assert saved.status_code == 200, saved.text
    assert (
        mutate(admin, path, {**body, "sets_a": 9}, **{"Idempotency-Key": str(key)}).status_code
        == 409
    )
    assert mutate(admin, path, body, **{"Idempotency-Key": str(uuid4())}).status_code == 409


def test_bad_scores_and_roster_correction_do_not_mutate_data(calendar_system):
    _, _, admin, _, member, _, meeting, ids = prepare(calendar_system)
    for sets in [
        {"sets_a": True, "sets_b": 1},
        {"sets_a": -1, "sets_b": 2},
        {"sets_a": 3.5, "sets_b": 2},
    ]:
        assert (
            mutate(
                admin,
                f"/admin/meetings/{meeting['id']}/result-preview",
                {"expected_version": fresh(admin, meeting)["version"], **sets},
            ).status_code
            == 422
        )
    save(admin, meeting)
    a, b = team_ids(member, meeting)
    correction = {
        "expected_version": fresh(admin, meeting)["version"],
        "sets_a": 5,
        "sets_b": 3,
        "reason": "Poprawka",
        "team_a": [ids[4], *a[1:]],
        "team_b": b,
    }
    assert (
        mutate(
            admin, f"/admin/meetings/{meeting['id']}/result-correction-preview", correction
        ).status_code
        == 422
    )
    correction["team_a"] = [a[0], a[0]]
    assert (
        mutate(
            admin, f"/admin/meetings/{meeting['id']}/result-correction-preview", correction
        ).status_code
        == 422
    )
    assert result(member, meeting)["revision"] == 1


def test_concurrent_results_are_serialized_and_rankings_preserve_blocked_profiles(calendar_system):
    from concurrent.futures import ThreadPoolExecutor

    from tests.test_auth import login

    device, clock, admin, actor, member, _, meeting, ids = prepare(calendar_system)
    a, b = team_ids(member, meeting)
    body, view = preview(admin, meeting)
    second = second_match(admin, clock, ids[:4], a, b)
    other_body, other_view = preview(admin, second)
    body["expected_rating_version"] = view["rating_version"]
    other_body["expected_rating_version"] = other_view["rating_version"]
    other_admin = device()
    assert login(other_admin, actor, pin="123456").status_code == 200

    def send(args):
        client, target, payload = args
        return mutate(
            client,
            f"/admin/meetings/{target['id']}/result",
            payload,
            **{"Idempotency-Key": str(uuid4())},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(send, [(admin, meeting, body), (other_admin, second, other_body)])
        )
    assert sorted(r.status_code for r in responses) == [200, 409]
    winner = meeting if responses[0].status_code == 200 else second
    loser = second if winner == meeting else meeting
    save(admin, loser)
    assert len(member.get(PREFIX + "/results").json()["items"]) == 2
    assert (
        mutate(admin, f"/admin/players/{ids[0]}", {"is_active": False}, "PATCH").status_code == 200
    )
    ranked = member.get(PREFIX + "/ranking?limit=100").json()
    player = next(p for p in ranked["items"] if p["player"]["id"] == ids[0])
    assert (
        player["meetings"] == 2
        and "priority_status" not in str(ranked)
        and "is_active" not in str(ranked)
    )
    assert member.get(PREFIX + "/ranking?limit=1").json()["next_offset"] == 1
    assert len(member.get(PREFIX + "/results?limit=1&offset=1").json()["items"]) == 1


def test_current_ratings_drive_balanced_teams(calendar_system):
    _, clock, admin, _, member, _, meeting, ids = prepare(calendar_system)
    a, b = team_ids(member, meeting)
    save(admin, meeting, 5, 0)
    second = second_match(admin, clock, ids[:4], a, b, manual=False)
    second_a, second_b = team_ids(member, second)
    assert len(set(second_a) & set(a)) == len(set(second_b) & set(a)) == 1
    teams = member.get(PREFIX + f"/meetings/{second['id']}/teams").json()
    assert teams["average_a"] == teams["average_b"] == 1000
    assert {Decimal(str(p["rating"])) for p in teams["team_a"]} == {Decimal(1016), Decimal(984)}


def test_unequal_team_sizes_keep_equal_delta_within_each_side():
    ids = [UUID(int=i + 1) for i in range(13)]
    match = Match(
        uuid4(), uuid4(), datetime(2026, 11, 10, tzinfo=UTC), tuple(ids[:6]), tuple(ids[6:]), 5, 0
    )
    ratings, _, entries, _ = replay([match])
    assert len(entries) == 13
    assert all(ratings[p] == 1016 for p in ids[:6]) and all(ratings[p] == 984 for p in ids[6:])
    assert sum(e.delta for e in entries) == -16  # 6 versus 7; do not change the per-team rule.


def test_global_rating_lock_without_http_identity_lock(calendar_system):
    import asyncio
    import os

    from sqlalchemy import func, select

    from app.api.errors import DomainError
    from app.api.result_schemas import SaveResult
    from app.core.database import Database
    from app.models.results import RatingEntry, ResultRevision
    from app.services import results as service

    _, clock, admin, actor, _, _, first, ids = prepare(calendar_system)
    a, b = team_ids(admin, first)
    second = second_match(admin, clock, ids[:4], a, b)
    body1, view1 = preview(admin, first)
    body2, view2 = preview(admin, second)
    body1["expected_rating_version"] = view1["rating_version"]
    body2["expected_rating_version"] = view2["rating_version"]

    async def race():
        database = Database(os.environ["VOLLEYCREW_TEST_DATABASE_URL"])
        try:

            async def one(meeting, body):
                async with database.sessions() as db:
                    try:
                        await service.save(
                            db,
                            UUID(meeting["id"]),
                            SaveResult(**body),
                            UUID(actor["id"]),
                            uuid4(),
                            clock,
                        )
                        await db.commit()
                        return "accepted"
                    except DomainError as error:
                        await db.rollback()
                        return error.code

            responses = await asyncio.gather(one(first, body1), one(second, body2))
            assert sorted(responses) == ["accepted", "version_conflict"]
            async with database.sessions() as db:
                assert await db.scalar(select(func.count()).select_from(ResultRevision)) == 1
                assert await db.scalar(select(func.count()).select_from(RatingEntry)) == 4
        finally:
            await database.engine.dispose()

    asyncio.run(race())
