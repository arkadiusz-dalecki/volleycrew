import { useAdminView } from "../auth/ViewMode";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useState } from "react";
import {
  ArrowRight,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  MapPin,
} from "lucide-react";
import { api, unwrap } from "../../lib/api/client";
import { dateLabel, hour, localDate, shiftMonth, statusLabel } from "./dates";
import { useOpenMeeting } from "./useOpenMeeting";

import { ScheduleEditor } from "../schedule/ScheduleEditor";
import { MeetingActions } from "../schedule/MeetingActions";
import { CreateMeeting } from "../schedule/CreateMeeting";

export function CalendarPage() {
  const adminView = useAdminView();
  const [action, setAction] = useState<"single" | "series" | null>(null);
  const [params, setParams] = useSearchParams();
  const rawMonth = params.get("month") ?? "";
  const month =
    /^\d{4}-(0[1-9]|1[0-2])$/.test(rawMonth) &&
    rawMonth >= "1970-01" &&
    rawMonth <= "9997-12"
      ? rawMonth
      : localDate(new Date().toISOString()).slice(0, 7);
  const [notice, setNotice] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const opener = useOpenMeeting();
  const start = `${month}-01`,
    end = `${shiftMonth(month, 1)}-01`;
  const calendar = useQuery({
    queryKey: ["calendar", month],
    queryFn: async ({ signal }) => {
      const first = unwrap(
        await api.GET("/api/v1/calendar", {
          params: { query: { from: start, to: end, limit: 100 } },
          signal,
        }),
      );
      // Follow server pagination, including future exception-heavy months.
      let offset = first.next_offset;
      while (offset !== null) {
        const next = unwrap(
          await api.GET("/api/v1/calendar", {
            params: { query: { from: start, to: end, limit: 100, offset } },
            signal,
          }),
        );
        first.items.push(...next.items);
        offset = next.next_offset;
      }
      return first;
    },
    refetchInterval: 30_000,
  });
  const [year, number] = month.split("-").map(Number);
  const count = new Date(Date.UTC(year, number, 0)).getUTCDate();
  const pad = (new Date(Date.UTC(year, number - 1, 1)).getUTCDay() + 6) % 7;
  const days = Array.from(
    { length: Math.ceil((pad + count) / 7) * 7 },
    (_, i) => i - pad + 1,
  );
  const title = new Intl.DateTimeFormat("pl-PL", {
    timeZone: "UTC",
    month: "long",
    year: "numeric",
  }).format(new Date(`${start}T12:00:00Z`));
  const items = calendar.data?.items ?? [];
  const visible = selected
    ? items.filter((item) => localDate(item.starts_at) === selected)
    : items;
  function move(shift: number) {
    setSelected(null);
    setParams({ month: shiftMonth(month, shift) });
  }
  return (
    <>
      <div className="page-heading">
        <h1>Kalendarz</h1>
        <p>Zarezerwuj sobie czas na grę. Wybierz miesiąc i sprawdź terminy.</p>
      </div>
      {adminView && (
        <div className="calendar-admin">
          <div className="row-actions">
            <button
              className="button primary"
              aria-expanded={action === "single"}
              onClick={() => setAction(action === "single" ? null : "single")}
            >
              Dodaj spotkanie
            </button>
            <button
              className="button"
              aria-expanded={action === "series"}
              onClick={() => setAction(action === "series" ? null : "series")}
            >
              Zaplanuj serię
            </button>
          </div>
          <p className="form-note">
            Termin zmienisz lub odwołasz bezpośrednio na kafelku spotkania.
          </p>
          {action === "single" && (
            <CreateMeeting
              key={selected ?? month}
              date={
                selected ??
                (month === localDate(new Date().toISOString()).slice(0, 7)
                  ? localDate(new Date().toISOString())
                  : `${month}-01`)
              }
            />
          )}
          {action === "series" && <ScheduleEditor />}
        </div>
      )}
      <div className="calendar-layout">
        <div className="calendar-month-column">
          <div className="section-title calendar-column-heading">
            <h2>Wybierz dzień</h2>
          </div>
          <section className="card calendar-card">
            <div className="calendar-toolbar">
              <button
                className="button calendar-arrow"
                aria-label="Poprzedni miesiąc"
                disabled={month === "1970-01"}
                onClick={() => move(-1)}
              >
                <ChevronLeft size={20} />
              </button>
              <h2 aria-live="polite">{title}</h2>
              <button
                className="button calendar-arrow"
                aria-label="Następny miesiąc"
                disabled={month === "9997-12"}
                onClick={() => move(1)}
              >
                <ChevronRight size={20} />
              </button>
            </div>
            <div className="calendar-jump">
              <label>
                Miesiąc
                <input
                  type="month"
                  value={month}
                  min="1970-01"
                  max="9997-12"
                  onChange={(e) => {
                    if (e.target.validity.valid && e.target.value) {
                      setSelected(null);
                      setParams({ month: e.target.value });
                    }
                  }}
                />
              </label>
              <button
                className="button small"
                onClick={() => {
                  setSelected(null);
                  setParams({});
                }}
              >
                Dzisiaj
              </button>
            </div>
            <table className="month-grid" aria-label={title}>
              <thead>
                <tr>
                  {["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"].map((day) => (
                    <th scope="col" key={day}>
                      {day}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: days.length / 7 }, (_, week) => (
                  <tr key={week}>
                    {days.slice(week * 7, week * 7 + 7).map((day, col) => {
                      const key = `${month}-${String(day).padStart(2, "0")}`;
                      const events = items.filter(
                        (item) => localDate(item.starts_at) === key,
                      );
                      const today = key === localDate(new Date().toISOString());
                      return (
                        <td key={col}>
                          {day < 1 || day > count ? null : (
                            <button
                              className={`calendar-day ${today ? "today" : ""} ${selected === key ? "selected" : ""}`}
                              disabled={!events.length && !adminView}
                              aria-label={`${day} ${title}${events.length ? `, spotkania: ${events.length}${events.every((item) => item.status === "cancelled") ? ", odwołane" : ""}` : ""}`}
                              aria-pressed={selected === key}
                              onClick={() =>
                                setSelected(selected === key ? null : key)
                              }
                            >
                              <span>{day}</span>
                              {events.length > 0 && (
                                <i
                                  className={
                                    events.every(
                                      (item) => item.status === "cancelled",
                                    )
                                      ? "cancelled-dot"
                                      : "event-dot"
                                  }
                                />
                              )}
                            </button>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="calendar-legend">
              <span>
                <i className="event-dot" /> Spotkanie
              </span>
              <span>
                <i className="cancelled-dot" /> Odwołane
              </span>
            </div>
          </section>
        </div>
        <section className="calendar-agenda">
          <div className="section-title">
            <h2>
              {selected
                ? `Terminy · ${selected.split("-").reverse().join(".")}`
                : "Spotkania w tym miesiącu"}
            </h2>
            {selected && (
              <button
                className="button small"
                onClick={() => setSelected(null)}
              >
                Cały miesiąc
              </button>
            )}
          </div>
          {notice && (
            <p className="form-notice" role="status">
              {notice}
            </p>
          )}
          {calendar.isPending ? (
            <div className="card" role="status">
              Wczytujemy terminy…
            </div>
          ) : calendar.isError && !calendar.data ? (
            <div className="card" role="alert">
              <h3>Nie udało się pobrać kalendarza</h3>
              <p className="form-note">
                Sprawdź połączenie i spróbuj ponownie.
              </p>
              <button
                className="button"
                onClick={() => void calendar.refetch()}
              >
                Ponów
              </button>
            </div>
          ) : (
            <>
              {calendar.isError && (
                <p className="form-error" role="alert">
                  Dane mogą być nieaktualne.{" "}
                  <button
                    className="button small"
                    onClick={() => void calendar.refetch()}
                  >
                    Ponów
                  </button>
                </p>
              )}
              {!visible.length ? (
                <div className="card empty-state">
                  <CalendarDays size={30} />
                  <h3>Brak spotkań</h3>
                  <p>
                    W tym zakresie nie ma zaplanowanej gry ani zapisanych
                    spotkań.
                  </p>
                </div>
              ) : (
                <ul className="agenda-list">
                  {visible.map((item) => (
                    <li
                      className={`card agenda-card ${item.status === "cancelled" ? "cancelled" : ""}`}
                      key={item.id}
                    >
                      <div className="agenda-date">
                        <span>
                          {new Intl.DateTimeFormat("pl-PL", {
                            day: "2-digit",
                            timeZone: "Europe/Warsaw",
                          }).format(new Date(item.starts_at))}
                        </span>
                        <small>
                          {new Intl.DateTimeFormat("pl-PL", {
                            weekday: "short",
                            timeZone: "Europe/Warsaw",
                          }).format(new Date(item.starts_at))}
                        </small>
                      </div>
                      <div className="agenda-copy">
                        <span className={`meeting-state ${item.status}`}>
                          {statusLabel[item.status]}
                        </span>
                        <h3>{dateLabel(item.starts_at, item.timezone)}</h3>
                        <p>
                          <Clock3 size={14} />
                          {hour(item.starts_at, item.timezone)} —{" "}
                          {hour(item.ends_at, item.timezone)}
                        </p>
                        <p>
                          <MapPin size={14} />
                          {item.venue}
                        </p>
                        <small>
                          {item.participant_count} / {item.capacity} uczestników
                        </small>
                      </div>
                      <button
                        className="button agenda-open"
                        aria-label={`Otwórz spotkanie: ${dateLabel(item.starts_at, item.timezone)}`}
                        disabled={!!opener.busy}
                        onClick={() => void opener.open(item)}
                      >
                        <ArrowRight size={18} />
                      </button>
                      {adminView && (
                        <MeetingActions
                          meeting={item}
                          compact
                          onChanged={(updated, resultNotice) => {
                            const date = localDate(updated.starts_at);
                            if (selected || date.slice(0, 7) !== month)
                              setSelected(date);
                            if (date.slice(0, 7) !== month)
                              setParams({ month: date.slice(0, 7) });
                            setNotice(resultNotice);
                          }}
                        />
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
          {opener.error && (
            <p className="form-error" role="alert">
              {opener.error}
            </p>
          )}
        </section>
      </div>
    </>
  );
}
