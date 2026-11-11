import { describe, expect, it } from "vitest";
import { calendarFile, calendarUrl } from "./calendarExport";

const meeting = {
  id: "59a3e838-7aba-46a6-98dd-c2e532090dbc",
  starts_at: "2026-11-10T18:00:00+01:00",
  ends_at: "2026-11-10T20:00:00+01:00",
  timezone: "Europe/Warsaw",
  venue: "I LO w Gdańsku",
  term_version: 2,
};

describe("calendar export", () => {
  it("keeps the same instant in winter and summer for calendar providers", () => {
    for (const [start, end, expected] of [
      [meeting.starts_at, meeting.ends_at, "20261110T170000Z/20261110T190000Z"],
      [
        "2026-07-07T18:00:00+02:00",
        "2026-07-07T20:00:00+02:00",
        "20260707T160000Z/20260707T180000Z",
      ],
    ]) {
      const value = { ...meeting, starts_at: start, ends_at: end };
      const google = new URL(calendarUrl(value, "google"));
      expect(google.origin).toBe("https://calendar.google.com");
      expect(google.searchParams.get("dates")).toBe(expected);
      expect(google.searchParams.get("location")).toBe(meeting.venue);
      expect(google.searchParams.get("ctz")).toBe("Europe/Warsaw");
      for (const provider of ["outlook", "office365"] as const) {
        const url = new URL(calendarUrl(value, provider));
        expect(url.searchParams.get("startdt")).toBe(
          new Date(start).toISOString(),
        );
        expect(url.searchParams.get("enddt")).toBe(new Date(end).toISOString());
        expect(url.searchParams.get("location")).toBe(meeting.venue);
      }
    }
  });
  it("exports an interoperable UTC event with a stable identity", () => {
    const file = calendarFile(meeting, new Date("2026-11-08T10:00:00Z"));
    expect(file).toContain(
      "UID:59a3e838-7aba-46a6-98dd-c2e532090dbc@volleycrew\r\n",
    );
    expect(file).toContain(
      "DTSTART:20261110T170000Z\r\nDTEND:20261110T190000Z\r\n",
    );
    expect(file).toContain("DTSTAMP:20261108T100000Z\r\n");
    expect(file).toContain("LOCATION:I LO w Gdańsku\r\n");
    expect(file).toContain("SEQUENCE:2\r\n");
    expect(file).not.toContain("ATTENDEE");
    expect(file).not.toContain("hassio_ingress");
    expect(file.endsWith("END:VCALENDAR\r\n")).toBe(true);
  });
  it("escapes newlines and delimiters and folds Polish UTF-8 text at 75 octets", () => {
    const venue = "Sala; Gdańsk, \\" + "Żółć".repeat(30) + "\r\nBEGIN:VEVENT";
    const file = calendarFile({ ...meeting, venue });
    const unfolded = file.replace(/\r\n /g, "");
    expect(unfolded).toContain("LOCATION:Sala\\; Gdańsk\\, \\\\");
    expect(unfolded).toContain("\\nBEGIN:VEVENT\r\n");
    expect(
      file.split("\r\n").filter((line) => line === "BEGIN:VEVENT"),
    ).toHaveLength(1);
    expect(
      file
        .split("\r\n")
        .every((line) => new TextEncoder().encode(line).length <= 75),
    ).toBe(true);
    expect(unfolded).toContain("Żółć".repeat(30));
  });
});
