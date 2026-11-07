from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4

from app.services.signature_list import SignatureList, render_pdf
from tests.test_auth import PREFIX
from tests.test_auth import system as system
from tests.test_enrollment import as_player, declaration, setup_group
from tests.test_meetings import calendar_system as calendar_system
from tests.test_room import change, confirm, draft, read, start

NAMES = (
    "Michał Nowak",
    "Tomasz Wójcik",
    "Anna Kamińska",
    "Paweł Szymański",
    "Julia Woźniak",
    "Kamil Wiśniewski",
    "Piotr Zieliński",
    "Mateusz Lewandowski",
    "Katarzyna Dąbrowska",
    "Jakub Kozłowski",
    "Marta Jankowska",
    "Aleksandra Brzęczyszczykiewicz-Kowalska",
    "Marcin Kowal",
    "Agnieszka Malinowska",
)


def sample(names=NAMES):
    return SignatureList(
        datetime(2026, 11, 10, 17, tzinfo=UTC),
        datetime(2026, 11, 10, 19, tzinfo=UTC),
        "Europe/Warsaw",
        1,
        names,
    )


def extract(pdf):
    return " ".join(" ".join(page.extract_text().split()) for page in PdfReader(BytesIO(pdf)).pages)


def test_fourteen_names_print_on_one_a4_with_embedded_polish_font():
    pdf = render_pdf(sample())
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) == 1
    assert tuple(float(v) for v in reader.pages[0].mediabox[2:]) == pytest.approx(A4)
    text = extract(pdf)
    for name in NAMES:
        assert name in text
    assert all(
        label in text
        for label in [
            "Lista uczestników",
            "I LO w Gdańsku",
            "10.11.2026",
            "18:00 - 20:00",
            "Lp.",
            "Imię i nazwisko",
            "Podpis",
            "Liczba uczestników: 14",
        ]
    )
    resources = reader.pages[0]["/Resources"]["/Font"]
    for font in resources.values():
        descriptor = font.get_object().get("/FontDescriptor")
        if descriptor:
            assert "/FontFile2" in descriptor
    assert any("/FontDescriptor" in font.get_object() for font in resources.values())
    # Same input yields the same printable file; no hidden generation-time metadata.
    assert render_pdf(sample()) == pdf


def test_empty_roster_and_literal_markup_are_safe():
    assert "Brak potwierdzonych obecnych osób." in extract(render_pdf(sample(())))
    literal = "<b>Łukasz & Żaneta</b>"
    assert literal in extract(render_pdf(sample((literal,))))


def test_maximum_length_names_paginate_without_losing_rows():
    names = tuple(f"{index:02d}" + "W" * 78 + " " + "Ż" * 80 for index in range(14))
    reader = PdfReader(BytesIO(render_pdf(sample(names))))
    assert 1 < len(reader.pages) <= 3
    text = "".join(page.extract_text() for page in reader.pages).replace("\n", "").replace(" ", "")
    for name in names:
        assert name.replace(" ", "") in text
    for page in reader.pages:
        assert "Imię i nazwisko" in page.extract_text()
        assert tuple(float(v) for v in page.mediabox[2:]) == pytest.approx(A4)


def test_parallel_rendering_keeps_documents_separate():
    sources = [replace(sample(), names=(name,)) for name in NAMES[:4]]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(render_pdf, sources))
    for index, pdf in enumerate(results):
        text = extract(pdf)
        assert NAMES[index] in text
        assert all(other not in text for i, other in enumerate(NAMES[:4]) if i != index)


def test_requires_admin_confirmed_presence_and_reads_latest_correction(calendar_system):
    device, clock, admin, _, member, player, meeting, ids = setup_group(calendar_system, 3)
    endpoint = PREFIX + f"/admin/meetings/{meeting['id']}/signature-list"
    assert member.get(endpoint).status_code == 403
    assert device().get(endpoint).status_code == 401
    assert admin.get(endpoint).status_code == 409
    assert draft(admin, meeting, [ids[2]]).status_code == 200
    assert admin.get(endpoint).status_code == 409
    start(clock, meeting)
    view = confirm(admin, meeting)
    before = read(admin, meeting)
    response = admin.get(endpoint)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-attendance-revision"] == "1"
    text = extract(response.content)
    assert "Gracz0 Testowy" in text and "Gracz1 Testowy" in text and "Gracz2 Testowy" not in text
    assert player["first_name"] not in text  # unsaved member profile is not a participant
    assert read(admin, meeting) == before  # read-only operation never modifies attendance/version
    source = next(p["event_id"] for p in view["players"] if p["player"]["id"] == ids[1])
    result = change(
        admin,
        meeting,
        "attendance/corrections",
        {"event_id": source, "value": "no_show", "reason": "Nie dotarł na salę"},
    )
    assert result.status_code == 200
    corrected = admin.get(endpoint + "?download=true")
    assert (
        corrected.headers["content-disposition"]
        == 'attachment; filename="lista-podpisow-2026-11-10.pdf"'
    )
    assert corrected.headers["x-attendance-revision"] == "2"
    assert "Gracz1 Testowy" not in extract(corrected.content)
    assert "Nie dotarł" not in extract(corrected.content)
    assert "Liczba uczestników: 1" in extract(corrected.content)


def test_cancelled_unknown_and_reserved_profiles_are_excluded(calendar_system):
    from uuid import uuid4

    device, clock, admin, _, member, _, meeting, ids = setup_group(calendar_system)
    assert declaration(member, meeting).status_code == 200  # waiting, never confirmed
    assert draft(admin, meeting, [ids[0]]).status_code == 200
    start(clock, meeting)
    confirm(admin, meeting)  # reserves the freed place for member, does not admit them
    endpoint = PREFIX + f"/admin/meetings/{meeting['id']}/signature-list"
    text = extract(admin.get(endpoint).content)
    assert "Gracz0 Testowy" not in text and "Liczba uczestników: 13" in text
    assert admin.get(PREFIX + f"/admin/meetings/{uuid4()}/signature-list").status_code == 404
    # A fresh future meeting can be cancelled without attendance; no document is released.
    from tests.test_meetings import resolve_day

    future = resolve_day(admin, day="2026-11-17")
    assert change(admin, future, "cancel").status_code == 200
    assert admin.get(PREFIX + f"/admin/meetings/{future['id']}/signature-list").status_code == 409
    assert as_player(device, ids[1]).get(endpoint + "?download=true").status_code == 403


if __name__ == "__main__":
    # Explicit QA fixture only; no production/personal data, outside the application runtime.
    root = Path(__file__).resolve().parents[3] / "output" / "pdf"
    root.mkdir(parents=True, exist_ok=True)
    (root / "e7-lista-podpisow-przyklad.pdf").write_bytes(render_pdf(sample()))
    (root / "e7-lista-podpisow-skrajne-nazwiska.pdf").write_bytes(
        render_pdf(sample(tuple(f"{i:02d}" + "W" * 78 + " " + "Ż" * 80 for i in range(14))))
    )
    print(root)
