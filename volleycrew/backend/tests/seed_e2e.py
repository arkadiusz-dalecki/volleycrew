"""Opt-in disposable data for Playwright; refuses every non-*_test database."""

import asyncio
import json
import sys
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.clock import SystemClock
from app.core.config import get_settings
from app.core.database import Database
from app.core.security import hash_pin, new_token, token_hash
from app.domain.schedule import first_date_on_or_after
from app.models.auth import Invite, Player
from app.services.enrollment import declare
from app.services.meetings import resolve
from tests.calendar_support import DEFAULT_ID, reset_calendar


async def main():
    settings = get_settings()
    url = settings.database_url.get_secret_value()
    if not make_url(url).database.endswith("_test"):
        raise SystemExit("E2E seed requires a disposable database ending in _test")
    database = Database(url)
    try:
        async with database.sessions() as db:
            if sys.argv[1:] == ["--reset-limits"]:
                await db.execute(text("TRUNCATE auth_throttles"))
                await db.commit()
                return
            await db.execute(text("TRUNCATE players, bootstrap_grants, auth_throttles CASCADE"))
            await reset_calendar(db)
            at = SystemClock().now()
            player = Player(
                first_name="Arkadiusz",
                last_name="Testowy",
                nickname="E2E",
                priority_status="founder",
                role="admin",
                pin_hash=await hash_pin("123456"),
                created_at=at,
            )
            db.add(player)
            await db.flush()
            token = new_token()
            db.add(Invite(token_hash=token_hash(token), created_by=player.id, created_at=at))
            target = at.date() + timedelta(days=90)
            month_start = date(target.year, target.month, 1)
            cancelled = await resolve(db, DEFAULT_ID, first_date_on_or_after(month_start, 1), at)
            cancelled.status = "cancelled"
            enrollment_meetings = {}
            for index, project in enumerate(["desktop", "mobile", "webkit"]):
                full = await resolve(
                    db, DEFAULT_ID, cancelled.source_date + timedelta(days=7 * (index + 1)), at
                )
                enrollment_meetings[project] = str(full.id)
                await declare(db, full.id, player, "going", 1, at, uuid4())
                for number in range(13):
                    person = Player(
                        first_name=f"Zawodnik {number + 1}",
                        last_name="Testowy",
                        nickname=project,
                        priority_status="guest",
                        role="player",
                        pin_hash=player.pin_hash,
                        created_at=at,
                    )
                    db.add(person)
                    await db.flush()
                    await declare(db, full.id, person, "going", 1, at, uuid4())
            room_meetings = {}
            for index, project in enumerate(["desktop", "mobile", "webkit"]):
                room_meeting = await resolve(
                    db, DEFAULT_ID, cancelled.source_date + timedelta(days=7 * (index + 5)), at
                )
                attendees = []
                for first, last in [
                    ("Michał", "Nowak"),
                    ("Tomasz", "Wójcik"),
                    ("Anna", "Kamińska"),
                    ("Paweł", "Szymański"),
                    ("Julia", "Woźniak"),
                    ("Kamil", "Wiśniewski"),
                    ("Piotr", "Zieliński"),
                    ("Mateusz", "Lewandowski"),
                    ("Katarzyna", "Dąbrowska"),
                    ("Jakub", "Kozłowski"),
                    ("Marta", "Jankowska"),
                    ("Aleksandra", "Brzęczyszczykiewicz-Kowalska"),
                    ("Marcin", "Kowal"),
                    ("Agnieszka", "Malinowska"),
                ]:
                    person = Player(
                        first_name=first,
                        last_name=last,
                        nickname=f"Sala {project}",
                        priority_status="guest",
                        role="player",
                        pin_hash=player.pin_hash,
                        created_at=at,
                    )
                    db.add(person)
                    await db.flush()
                    await declare(db, room_meeting.id, person, "going", 1, at, uuid4())
                    attendees.append(str(person.id))
                # A running match, isolated per browser project. Only the disposable seeder
                # moves it to now; production mutations always use the scheduling service.
                room_meeting.starts_at = at - timedelta(minutes=15)
                room_meeting.ends_at = at + timedelta(minutes=105)
                room_meeting.is_exception = True
                room_meetings[project] = {"id": str(room_meeting.id), "players": attendees}
            await db.commit()
            print(
                json.dumps(
                    {
                        "admin_id": str(player.id),
                        "invite": token,
                        "calendar_month": month_start.strftime("%Y-%m"),
                        "cancelled_id": str(cancelled.id),
                        "enrollment_meetings": enrollment_meetings,
                        "room_meetings": room_meetings,
                    }
                )
            )
    finally:
        await database.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
