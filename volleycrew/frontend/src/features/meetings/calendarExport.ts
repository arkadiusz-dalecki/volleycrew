import type { components } from "../../lib/api/schema";

type Meeting = Pick<
  components["schemas"]["MeetingSummary"],
  "id" | "starts_at" | "ends_at" | "venue" | "timezone" | "term_version"
>;
export type WebCalendar = "google" | "outlook" | "office365";
const title = "Siatkówka · Volleycrew";
const description =
  "Spotkanie Volleycrew. Aktualny termin i swój udział sprawdź w Volleycrew. Zmiany terminu nie synchronizują się automatycznie z tym wpisem.";

function utc(value: string) {
  return new Date(value)
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\.\d{3}Z$/, "Z");
}

export function calendarUrl(meeting: Meeting, provider: WebCalendar) {
  if (provider === "google") {
    const url = new URL("https://calendar.google.com/calendar/render");
    url.search = new URLSearchParams({
      action: "TEMPLATE",
      text: title,
      dates: `${utc(meeting.starts_at)}/${utc(meeting.ends_at)}`,
      ctz: meeting.timezone,
      location: meeting.venue,
      details: description,
    }).toString();
    return url.href;
  }
  const url = new URL(
    provider === "office365"
      ? "https://outlook.office.com/calendar/0/deeplink/compose"
      : "https://outlook.live.com/calendar/0/deeplink/compose",
  );
  url.search = new URLSearchParams({
    path: "/calendar/action/compose",
    rru: "addevent",
    subject: title,
    startdt: new Date(meeting.starts_at).toISOString(),
    enddt: new Date(meeting.ends_at).toISOString(),
    location: meeting.venue,
    body: description,
    allday: "false",
  }).toString();
  return url.href;
}

function escapeText(value: string) {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/\r\n|\r|\n/g, "\\n")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,");
}

// RFC 5545 folds content lines at 75 octets, without splitting UTF-8 characters.
function fold(line: string) {
  const encoder = new TextEncoder();
  let part = "",
    size = 0;
  const parts: string[] = [];
  for (const character of line) {
    const bytes = encoder.encode(character).length;
    if (size + bytes > 75) {
      parts.push(part);
      part = " ";
      size = 1;
    }
    part += character;
    size += bytes;
  }
  parts.push(part);
  return parts.join("\r\n");
}

export function calendarFile(meeting: Meeting, now = new Date()) {
  return [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Volleycrew//Meeting//PL",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:${meeting.id}@volleycrew`,
    `DTSTAMP:${utc(now.toISOString())}`,
    `DTSTART:${utc(meeting.starts_at)}`,
    `DTEND:${utc(meeting.ends_at)}`,
    `SEQUENCE:${meeting.term_version}`,
    `SUMMARY:${escapeText(title)}`,
    `LOCATION:${escapeText(meeting.venue)}`,
    `DESCRIPTION:${escapeText(description)}`,
    "END:VEVENT",
    "END:VCALENDAR",
    "",
  ]
    .map(fold)
    .join("\r\n");
}

export function downloadCalendarFile(meeting: Meeting, filename: string) {
  const blob = new Blob([calendarFile(meeting)], {
    type: "text/calendar;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}
