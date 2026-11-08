"""Snapshot confirmed presence, then render a local, printable school document."""

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select

from app.api.errors import DomainError
from app.models.auth import Player
from app.models.room import Attendance
from app.services.enrollment import lock_meeting


@dataclass(frozen=True)
class SignatureList:
    starts_at: datetime
    ends_at: datetime
    timezone: str
    attendance_revision: int
    names: tuple[str, ...]

    @property
    def local_start(self):
        return self.starts_at.astimezone(ZoneInfo(self.timezone))

    @property
    def filename(self):
        return f"lista-podpisow-{self.local_start:%Y-%m-%d}.pdf"


async def snapshot(db, meeting_id):
    # The same lock as corrections/admissions: one consistent attendance revision.
    meeting = await lock_meeting(db, meeting_id)
    if meeting.status == "cancelled":
        raise DomainError(409, "meeting_cancelled", "Odwołane spotkanie nie ma listy podpisów.")
    if not meeting.attendance_confirmed_at or meeting.status not in {
        "attendance_checked",
        "teams_confirmed",
        "completed",
    }:
        raise DomainError(409, "attendance_required", "Najpierw zatwierdź faktyczną obecność.")
    rows = (
        await db.execute(
            select(Player.first_name, Player.last_name, Player.id)
            .join(Attendance, Attendance.player_id == Player.id)
            .where(Attendance.meeting_id == meeting.id, Attendance.confirmed_state == "present")
        )
    ).all()
    # Full names, including blocked historical profiles. Never nickname/priority/history.
    rows = sorted(rows, key=lambda p: (p.last_name.casefold(), p.first_name.casefold(), str(p.id)))
    result = SignatureList(
        meeting.starts_at,
        meeting.ends_at,
        meeting.timezone,
        meeting.attendance_revision,
        tuple(f"{p.first_name} {p.last_name}" for p in rows),
    )
    await db.commit()  # Release the roster lock before CPU work; no domain mutation.
    return result


@lru_cache(maxsize=1)
def register_fonts():
    root = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    for style, filename in [("Regular", "NotoSans-Regular.ttf"), ("Bold", "NotoSans-Bold.ttf")]:
        pdfmetrics.registerFont(TTFont(f"VolleycrewNoto{style}", str(root / filename)))


_render_lock = Lock()


def render_pdf(source: SignatureList) -> bytes:
    # ReportLab font subsetting uses shared registration state. Serialize rendering
    # in the worker pool, never on the asyncio event loop.
    with _render_lock:
        return _render_pdf(source)


def _render_pdf(source: SignatureList) -> bytes:
    register_fonts()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=17 * mm,
        bottomMargin=18 * mm,
        title="Lista uczestników",
        author="Volleycrew",
        invariant=1,
    )
    regular, bold = "VolleycrewNotoRegular", "VolleycrewNotoBold"
    title = ParagraphStyle("title", fontName=bold, fontSize=20, leading=26, spaceAfter=8)
    body = ParagraphStyle("body", fontName=regular, fontSize=10.5, leading=15)
    name = ParagraphStyle("name", parent=body, leading=13.5, splitLongWords=True)
    header = ParagraphStyle("header", parent=body, fontName=bold, fontSize=10)
    number = ParagraphStyle("number", parent=body, alignment=TA_CENTER)
    end = source.ends_at.astimezone(ZoneInfo(source.timezone))
    story = [
        Paragraph("Lista uczestników", title),
        Paragraph("I LO w Gdańsku", body),
        Spacer(1, 5 * mm),
        Paragraph(f"Data spotkania: {source.local_start:%d.%m.%Y}", body),
        Paragraph(f"Godziny: {source.local_start:%H:%M} - {end:%H:%M}", body),
        Paragraph(f"Liczba uczestników: {len(source.names)}", body),
        Spacer(1, 7 * mm),
    ]
    if source.names:
        data = [[Paragraph(text, header) for text in ["Lp.", "Imię i nazwisko", "Podpis"]]]
        for index, full_name in enumerate(source.names, 1):
            data.append([Paragraph(str(index), number), Paragraph(escape(full_name), name), ""])
        table = Table(
            data,
            colWidths=[12 * mm, 96 * mm, 72 * mm],
            repeatRows=1,
            minRowHeights=[11 * mm] + [14 * mm] * len(source.names),
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#626262")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f1f1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("Brak potwierdzonych obecnych osób.", body))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 8)
        canvas.setFillColor(colors.HexColor("#626262"))
        canvas.drawString(15 * mm, 10 * mm, "Volleycrew | Lista podpisów")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Strona {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
