from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.domain.teams import split_teams
from app.models.room import Attendance, PreliminaryTeams, TeamSheet
from tests.test_auth import PREFIX, login, mutate
from tests.test_auth import system as system
from tests.test_enrollment import as_player, declaration, setup_group
from tests.test_meetings import calendar_system as calendar_system
from tests.test_room import change, confirm, draft, start
from tests.test_schedule_changes import fresh, move


def read(client, meeting):
    response = client.get(PREFIX + f"/meetings/{meeting['id']}/preliminary-teams")
    assert response.status_code == 200, response.text
    return response.json()


def ids(view):
    return [[p["player"]["id"] for p in view[key]] for key in ["team_a", "team_b"]]


def save(client, meeting, shown, mode="balanced", a=None, b=None):
    return mutate(
        client,
        f"/admin/meetings/{meeting['id']}/preliminary-teams",
        {
            "roster_token": shown["roster_token"],
            "revision": shown["revision"],
            "mode": mode,
            "team_a": a or [],
            "team_b": b or [],
        },
        "PUT",
    )


@pytest.mark.parametrize("count", [0, 1, 2, 8, 14])
def test_live_read_has_exact_roster_and_no_mutations(calendar_system, count):
    _, _, admin, _, member, _, meeting, players = setup_group(calendar_system, count)
    before = fresh(admin, meeting)
    first = read(member, meeting)
    assert first == read(admin, meeting)
    assert first["participant_count"] == count and first["method"] == "balanced"
    a, b = ids(first)
    assert set(a + b) == (set(players[:count]) if count >= 2 else set())
    assert len(a + b) == len(set(a + b)) and abs(len(a) - len(b)) <= 1
    assert fresh(admin, meeting) == before
    assert "priority_status" not in str(first) and "pin_hash" not in str(first)

    async def inspect():
        async with admin.app.state.database.sessions() as db:
            for model in [Attendance, TeamSheet, PreliminaryTeams]:
                assert await db.scalar(select(func.count()).select_from(model)) == 0

    admin.portal.call(inspect)


def test_elo_drives_default_and_rank_change_invalidates_override(calendar_system):
    from app.models.results import PlayerRating

    _, _, admin, _, member, _, meeting, players = setup_group(calendar_system, 8)
    ratings = {UUID(p): Decimal(900 + i * 37) for i, p in enumerate(players[:8])}

    async def setup():
        async with admin.app.state.database.sessions() as db:
            for player, points in ratings.items():
                db.add(PlayerRating(player_id=player, points=points, meetings=0))
            await db.commit()

    admin.portal.call(setup)
    shown = read(member, meeting)
    assert ids(shown) == [list(map(str, side)) for side in split_teams(ratings, "balanced")]
    saved = save(admin, meeting, shown, "random").json()
    assert saved["method"] == "random"

    async def update():
        async with admin.app.state.database.sessions() as db:
            row = await db.get(PlayerRating, UUID(players[0]))
            row.points += Decimal(250)
            await db.commit()

    admin.portal.call(update)
    changed = read(member, meeting)
    assert changed["method"] == "balanced" and changed["roster_token"] != saved["roster_token"]


def test_manual_split_is_public_and_changes_in_roster_cannot_restore_old_override(calendar_system):
    _, _, admin, _, member, _, meeting, _ = setup_group(calendar_system, 4)
    shown = read(admin, meeting)
    a, b = ids(shown)
    a[0], b[0] = b[0], a[0]
    result = save(admin, meeting, shown, "manual", a, b)
    assert result.status_code == 200, result.text
    saved = result.json()
    assert ids(read(member, meeting)) == [a, b]
    assert saved["method"] == "manual"
    assert declaration(member, meeting).status_code == 200
    changed = read(member, meeting)
    assert changed["method"] == "balanced" and changed["participant_count"] == 5
    assert save(admin, meeting, saved, "manual", a, b).status_code == 409
    assert declaration(member, meeting, "not-going").status_code == 200
    reverted = read(member, meeting)
    assert reverted["participant_count"] == 4 and reverted["method"] == "balanced"
    assert reverted["roster_token"] != saved["roster_token"]


def test_waitlist_and_offers_excluded_and_reschedule_clears_preview(calendar_system):
    from tests.test_enrollment import propose

    device, _, admin, _, member, player, meeting, players = setup_group(calendar_system)
    assert declaration(member, meeting).status_code == 200
    assert read(member, meeting)["participant_count"] == 14
    assert declaration(as_player(device, players[0]), meeting, "not-going").status_code == 200
    proposed = propose(admin, fresh(admin, meeting), player["id"])
    shown = read(member, meeting)
    assert shown["participant_count"] == 13
    assert player["id"] not in sum(ids(shown), [])
    response = mutate(
        member, f"/offers/{proposed['id']}/accept", {"term_version": meeting["term_version"]}
    )
    assert response.status_code == 200
    assert read(member, meeting)["participant_count"] == 14
    moved = move(admin, fresh(admin, meeting))
    assert read(member, moved)["participant_count"] == 0


def test_admin_permissions_invalid_members_duplicates_and_simultaneous_overrides(calendar_system):
    device, _, admin, actor, member, _, meeting, _ = setup_group(calendar_system, 4)
    shown = read(member, meeting)
    a, b = ids(shown)
    assert save(member, meeting, shown).status_code == 403
    assert save(admin, meeting, shown, "manual", a, a).status_code == 422
    assert save(admin, meeting, shown, "manual", [str(uuid4()), *a[1:]], b).status_code == 422
    other = device()
    assert login(other, actor, "123456").status_code == 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda client: save(client, meeting, shown, "random"), [admin, other])
        )
    assert sorted(result.status_code for result in results) == [200, 409]
    assert read(member, meeting)["revision"] == 1


def test_official_teams_can_reuse_manual_preview_only_after_presence(calendar_system):
    _, clock, admin, _, member, _, meeting, _ = setup_group(calendar_system, 4)
    shown = read(member, meeting)
    a, b = ids(shown)
    a[0], b[0] = b[0], a[0]
    saved = save(admin, meeting, shown, "manual", a, b)
    assert saved.status_code == 200
    assert change(admin, meeting, "teams/generate", {"mode": "preliminary"}).status_code == 409
    assert draft(admin, meeting).status_code == 200
    start(clock, meeting)
    confirm(admin, meeting)
    assert read(member, meeting) is None
    assert save(admin, meeting, saved.json()).status_code == 409
    result = change(admin, meeting, "teams/generate", {"mode": "preliminary"})
    assert result.status_code == 200, result.text
    assert ids(result.json()) == [a, b] and result.json()["method"] == "manual"


def test_changed_actual_roster_falls_back_to_elo_and_deleted_has_no_preview(calendar_system):
    _, clock, admin, _, member, _, meeting, players = setup_group(calendar_system, 4)
    shown = read(member, meeting)
    assert save(admin, meeting, shown, "random").status_code == 200
    assert draft(admin, meeting, [players[0]]).status_code == 200
    start(clock, meeting)
    confirm(admin, meeting)
    result = change(admin, meeting, "teams/generate", {"mode": "preliminary"})
    assert result.status_code == 200, result.text
    assert set(sum(ids(result.json()), [])) == set(players[1:4])
    assert result.json()["method"] == "balanced"
    from tests.test_meetings import resolve_day

    future = resolve_day(admin, "2026-11-17")
    assert (
        mutate(
            admin, f"/admin/meetings/{future['id']}/delete", {"expected_version": future["version"]}
        ).status_code
        == 204
    )
    assert member.get(PREFIX + f"/meetings/{future['id']}/preliminary-teams").status_code == 404
