import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, message, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { dateLabel, hour, localDate } from "../meetings/dates";
import { refreshSchedule } from "./refresh";

type Meeting = components["schemas"]["MeetingDetail"];
export function MeetingActions({ meeting }: { meeting: Meeting }) {
  const [mode, setMode] = useState<"edit" | "cancel" | null>(null);
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
  async function change(cancel: boolean) {
    setBusy(true);
    setNotice("");
    try {
      if (cancel)
        unwrap(
          await api.POST("/api/v1/admin/meetings/{meeting_id}/cancel", {
            params: { path: { meeting_id: meeting.id } },
            body: { expected_version: reviewed! },
          }),
        );
      else
        unwrap(
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
      setNotice(
        cancel
          ? "Spotkanie odwołane. Poinformuj grupę na Messengerze."
          : "Termin zmieniony. Poinformuj grupę na Messengerze o nowym terminie i potwierdzeniach.",
      );
    } catch (e) {
      setNotice(message(e));
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
  if (meeting.status !== "scheduled") return null;
  return (
    <section className="card meeting-actions">
      <h2>Zarządzaj terminem</h2>
      <div className="participation-actions">
        <button
          className="button"
          disabled={busy}
          onClick={() => {
            setDay(localDate(meeting.starts_at));
            setTime(hour(meeting.starts_at));
            setDuration(
              Math.round(
                (Date.parse(meeting.ends_at) - Date.parse(meeting.starts_at)) /
                  60000,
              ),
            );
            setMode("edit");
            setReviewed(null);
          }}
        >
          Zmień ten termin
        </button>
        <button
          className="button"
          disabled={busy}
          onClickCapture={(event) => event.currentTarget.focus()}
          onClick={() => {
            setMode("cancel");
            setReviewed(meeting.version);
          }}
        >
          Odwołaj spotkanie
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
        </form>
      )}
      {mode && reviewed !== null && (
        <ConfirmDialog
          title={
            mode === "cancel"
              ? "Odwołać spotkanie?"
              : "Zatwierdzić nowy termin?"
          }
          busy={busy}
          onDismiss={() => {
            if (mode === "cancel") setMode(null);
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
            {mode === "cancel"
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
              {mode === "cancel"
                ? "Potwierdzam odwołanie"
                : "Zatwierdź nowy termin"}
            </button>
          </div>
        </ConfirmDialog>
      )}
      {!!meeting.awaiting_confirmation.length && (
        <>
          <h3>Czekamy na nowe potwierdzenie</h3>
          <ul className="offer-list">
            {meeting.awaiting_confirmation.map((player) => (
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
