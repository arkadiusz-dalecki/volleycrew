import { useEffect, useState } from "react";
import { CalendarPlus, Download, ExternalLink } from "lucide-react";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import type { components } from "../../lib/api/schema";
import {
  downloadCalendarFile,
  calendarUrl,
  type WebCalendar,
} from "./calendarExport";
import { dateLabel, hour, localDate } from "./dates";

const providers: { id: WebCalendar; label: string }[] = [
  { id: "google", label: "Google Calendar" },
  { id: "outlook", label: "Outlook.com" },
  { id: "office365", label: "Outlook · Microsoft 365" },
];
export function AddToCalendar({
  meeting,
  compact = false,
}: {
  meeting: components["schemas"]["MeetingSummary"];
  compact?: boolean;
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  const [open, setOpen] = useState(false);
  const [notice, setNotice] = useState("");
  if (
    meeting.status === "cancelled" ||
    meeting.status === "completed" ||
    Date.parse(meeting.ends_at) <= now
  )
    return null;
  function download(apple: boolean) {
    downloadCalendarFile(
      meeting,
      `volleycrew-${localDate(meeting.starts_at, meeting.timezone)}.ics`,
    );
    setNotice(
      apple
        ? "Otwórz pobrany plik w Kalendarzu na Macu. Na iPhonie możesz zaimportować plik .ics z wiadomości w aplikacji Mail."
        : "Zaimportuj pobrany plik .ics w swojej aplikacji kalendarza.",
    );
  }
  return (
    <div className={compact ? "agenda-calendar" : "meeting-calendar"}>
      <button
        className="button"
        onClick={(event) => {
          event.currentTarget.focus();
          setNotice("");
          setOpen(true);
        }}
      >
        <CalendarPlus size={18} /> Dodaj do kalendarza
      </button>
      {open && (
        <ConfirmDialog
          title="Do jakiego kalendarza dodać?"
          onDismiss={() => setOpen(false)}
        >
          <p>
            {dateLabel(meeting.starts_at, meeting.timezone)},{" "}
            {hour(meeting.starts_at, meeting.timezone)}–
            {hour(meeting.ends_at, meeting.timezone)} · {meeting.venue}
          </p>
          <ul className="calendar-providers">
            {providers.map((provider) => (
              <li key={provider.id}>
                <a
                  className="button"
                  href={calendarUrl(meeting, provider.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink size={16} />
                  {provider.label}
                </a>
              </li>
            ))}
            <li>
              <button className="button" onClick={() => download(true)}>
                <Download size={16} />
                Apple Calendar (.ics)
              </button>
            </li>
            <li>
              <button className="button" onClick={() => download(false)}>
                <Download size={16} />
                Inna aplikacja (.ics)
              </button>
            </li>
          </ul>
          <p className="form-note">
            Zapisz wydarzenie w wybranej aplikacji. To pojedynczy termin —
            późniejsze zmiany lub odwołanie aktualizujesz w swoim kalendarzu.
          </p>
          {notice && (
            <p className="form-notice" role="status">
              {notice}
            </p>
          )}
          <div className="row-actions">
            <button className="button" onClick={() => setOpen(false)}>
              Zamknij
            </button>
          </div>
        </ConfirmDialog>
      )}
    </div>
  );
}
