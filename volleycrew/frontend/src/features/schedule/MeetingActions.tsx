import { useNavigate } from "react-router-dom";
import { Pencil, CalendarX2, Trash2 } from "lucide-react";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, message, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { dateLabel, hour, localDate } from "../meetings/dates";
import { refreshSchedule } from "./refresh";

type Meeting = components["schemas"]["MeetingDetail"];
function isDetail(
  value: Meeting | components["schemas"]["MeetingSummary"],
): value is Meeting {
  return (
    "awaiting_confirmation" in value &&
    Array.isArray(value.awaiting_confirmation)
  );
}
export function MeetingActions({
  meeting: source,
  compact = false,
  onChanged,
  onDeleted,
}: {
  meeting: Meeting | components["schemas"]["MeetingSummary"];
  compact?: boolean;
  onChanged?: (meeting: Meeting, notice: string) => void;
  onDeleted?: (notice: string) => void;
}) {
  const navigate = useNavigate();
  const [now] = useState(() => Date.now());
  const [prepared, setPrepared] = useState<Meeting | null>(null);
  const meeting = prepared ?? source;
  const [mode, setMode] = useState<"edit" | "cancel" | "delete" | null>(null);
  const [day, setDay] = useState(localDate(meeting.starts_at));
  const [time, setTime] = useState(hour(meeting.starts_at));
  const [duration, setDuration] = useState(
    Math.round(
      (Date.parse(meeting.ends_at) - Date.parse(meeting.starts_at)) / 60000,
    ),
  );
  const [reviewed, setReviewed] = useState<number | null>(null);
  const [release, setRelease] = useState<string | null>(null);
  const [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const client = useQueryClient();
  async function begin(nextMode: "edit" | "cancel" | "delete") {
    setBusy(true);
    setNotice("");
    try {
      // Calendar slots may not yet have a persistent Meeting. Resolve only
      // after an organizer chooses an action, without leaving the calendar.
      const current = isDetail(source)
        ? source
        : source.persisted
          ? unwrap(
              await api.GET("/api/v1/meetings/{meeting_id}", {
                params: { path: { meeting_id: source.id } },
              }),
            )
          : unwrap(
              await api.POST("/api/v1/meetings/resolve", {
                body: {
                  schedule_version_id: source.schedule_version_id,
                  source_date: source.source_date,
                },
              }),
            );
      setPrepared(current);
      setDay(localDate(current.starts_at));
      setTime(hour(current.starts_at));
      setDuration(
        Math.round(
          (Date.parse(current.ends_at) - Date.parse(current.starts_at)) / 60000,
        ),
      );
      setMode(nextMode);
      setReviewed(nextMode !== "edit" ? current.version : null);
    } catch (e) {
      setNotice(message(e));
      await refreshSchedule(client);
    } finally {
      setBusy(false);
    }
  }
  async function change(cancel: boolean) {
    setBusy(true);
    setNotice("");
    try {
      if (mode === "delete") {
        const result = await api.POST(
          "/api/v1/admin/meetings/{meeting_id}/delete",
          {
            params: { path: { meeting_id: meeting.id } },
            body: { expected_version: reviewed! },
          },
        );
        if (!result.response.ok) unwrap(result);
        setMode(null);
        setReviewed(null);
        setPrepared(null);
        const text = "Spotkanie usunięte z kalendarza.";
        onDeleted?.(text);
        if (!compact)
          void navigate(
            `/calendar?month=${localDate(meeting.starts_at).slice(0, 7)}`,
          );
        return;
      }
      const updated = cancel
        ? unwrap(
            await api.POST("/api/v1/admin/meetings/{meeting_id}/cancel", {
              params: { path: { meeting_id: meeting.id } },
              body: { expected_version: reviewed! },
            }),
          )
        : unwrap(
            await api.POST("/api/v1/admin/meetings/{meeting_id}/reschedule", {
              params: { path: { meeting_id: meeting.id } },
              body: {
                expected_version: reviewed!,
                local_date: day,
                local_time: time,
                duration_minutes: duration,
              },
            }),
          );
      setMode(null);
      setReviewed(null);
      const resultNotice = cancel
        ? "Spotkanie odwołane. Poinformuj grupę na Messengerze."
        : "Termin zmieniony. Poinformuj grupę na Messengerze o nowym terminie i potwierdzeniach.";
      setPrepared(null);
      setNotice(compact ? "" : resultNotice);
      onChanged?.(updated, resultNotice);
    } catch (e) {
      setNotice(message(e));
      setPrepared(null);
      setReviewed(null);
    } finally {
      await refreshSchedule(client);
      setBusy(false);
    }
  }
  async function free(playerId: string) {
    setBusy(true);
    setNotice("");
    try {
      unwrap(
        await api.POST(
          "/api/v1/admin/meetings/{meeting_id}/release-reconfirmation",
          {
            params: { path: { meeting_id: meeting.id } },
            body: { expected_version: meeting.version, player_id: playerId },
          },
        ),
      );
      setRelease(null);
      setNotice("Miejsce zwolnione. Sprawdź propozycje dla osób z rezerwy.");
    } catch (e) {
      setNotice(message(e));
    } finally {
      await refreshSchedule(client);
      setBusy(false);
    }
  }
  if (
    !["scheduled", "cancelled"].includes(source.status) ||
    (source.status !== "cancelled" && Date.parse(source.starts_at) <= now)
  )
    return null;
  const awaiting =
    !compact && isDetail(meeting) ? meeting.awaiting_confirmation : [];
  return (
    <section
      className={compact ? "agenda-admin-actions" : "card meeting-actions"}
      aria-label={
        compact
          ? `Zarządzaj spotkaniem: ${dateLabel(source.starts_at)}`
          : undefined
      }
    >
      {!compact && <h2>Zarządzaj terminem</h2>}
      <div className="participation-actions">
        {source.status === "scheduled" && (
          <>
            <button
              className="button"
              disabled={busy}
              onClick={() => void begin("edit")}
            >
              {compact && <Pencil size={16} />}
              {compact ? "Zmień termin" : "Zmień ten termin"}
            </button>
            <button
              className="button"
              disabled={busy}
              onClickCapture={(event) => event.currentTarget.focus()}
              onClick={() => void begin("cancel")}
            >
              {compact && <CalendarX2 size={16} />}
              {compact ? "Odwołaj" : "Odwołaj spotkanie"}
            </button>
          </>
        )}
        <button
          className="button"
          disabled={busy}
          onClickCapture={(event) => event.currentTarget.focus()}
          onClick={() => void begin("delete")}
        >
          <Trash2 size={16} /> Usuń spotkanie
        </button>
      </div>
      {mode === "edit" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setReviewed(meeting.version);
          }}
        >
          <div className="form-row">
            <label className="form-field">
              Nowa data spotkania
              <input
                type="date"
                value={day}
                required
                disabled={busy}
                onChange={(e) => {
                  setDay(e.target.value);
                  setReviewed(null);
                }}
              />
            </label>
            <label className="form-field">
              Nowa godzina
              <input
                type="time"
                value={time}
                required
                disabled={busy}
                onChange={(e) => {
                  setTime(e.target.value);
                  setReviewed(null);
                }}
              />
            </label>
          </div>
          <label className="form-field">
            Czas spotkania (minuty)
            <input
              type="number"
              min={1}
              max={1440}
              value={duration}
              required
              disabled={busy}
              onChange={(e) => {
                setDuration(Number(e.target.value));
                setReviewed(null);
              }}
            />
          </label>
          <button
            className="button"
            disabled={busy}
            onClickCapture={(event) => event.currentTarget.focus()}
          >
            Pokaż zmianę terminu
          </button>
          <button
            className="button"
            type="button"
            disabled={busy}
            onClick={() => {
              setMode(null);
              setReviewed(null);
            }}
          >
            Zamknij edycję
          </button>
        </form>
      )}
      {mode && reviewed !== null && (
        <ConfirmDialog
          title={
            mode === "delete"
              ? "Usunąć spotkanie?"
              : mode === "cancel"
                ? "Odwołać spotkanie?"
                : "Zatwierdzić nowy termin?"
          }
          busy={busy}
          onDismiss={() => {
            if (mode !== "edit") setMode(null);
            setReviewed(null);
          }}
        >
          {notice && (
            <p role="alert" className="form-error">
              {notice}
            </p>
          )}
          <p>
            Dotychczas: {dateLabel(meeting.starts_at)},{" "}
            {hour(meeting.starts_at)}.
          </p>
          {mode === "edit" && (
            <p>
              Nowy termin: {day.split("-").reverse().join(".")}, {time} ·{" "}
              {duration} min.
            </p>
          )}
          <p>
            {mode === "delete"
              ? "Spotkanie zniknie z kalendarza i nie pojawi się ponownie w serii. Zapisy i propozycje zostaną zamknięte, bez oznaczeń nieobecności. Pozostałe terminy serii pozostaną."
              : mode === "cancel"
                ? "Spotkanie pozostanie w kalendarzu jako odwołane. Miejsca i propozycje zostaną zwolnione; bez oznaczeń nieobecności."
                : "Wszyscy zapisani potwierdzają udział od nowa. Dotychczasowe miejsca pozostają zarezerwowane bez automatycznego timeoutu; stare propozycje przestają obowiązywać."}
          </p>
          <div className="participation-actions">
            <button
              className="button"
              disabled={busy}
              onClick={() => {
                setMode(null);
                setReviewed(null);
              }}
            >
              Anuluj zmianę
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => void change(mode === "cancel")}
            >
              {mode === "delete"
                ? "Usuń spotkanie"
                : mode === "cancel"
                  ? "Potwierdzam odwołanie"
                  : "Zatwierdź nowy termin"}
            </button>
          </div>
        </ConfirmDialog>
      )}
      {!!awaiting.length && (
        <>
          <h3>Czekamy na nowe potwierdzenie</h3>
          <ul className="offer-list">
            {awaiting.map((player) => (
              <li key={player.id}>
                <strong>
                  {player.first_name} {player.last_name}
                </strong>
                <button
                  className="button small"
                  disabled={busy}
                  onClick={() => setRelease(player.id)}
                >
                  Zwolnij oczekujące miejsce
                </button>
                {release === player.id && (
                  <div className="inline-confirmation">
                    <p>
                      Wycofasz oczekujące zgłoszenie tej osoby. Kolejna osoba z
                      rezerwy otrzyma rezerwację wymagającą potwierdzenia.
                    </p>
                    <div className="participation-actions">
                      <button
                        className="button small"
                        disabled={busy}
                        onClick={() => setRelease(null)}
                      >
                        Zachowaj miejsce
                      </button>
                      <button
                        className="button primary small"
                        disabled={busy}
                        onClick={() => void free(player.id)}
                      >
                        Potwierdź zwolnienie
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="form-notice" role="status">
        {notice}
      </p>
    </section>
  );
}
