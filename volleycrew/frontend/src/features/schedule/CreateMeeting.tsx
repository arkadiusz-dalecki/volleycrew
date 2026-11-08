import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, message, unwrap } from "../../lib/api/client";
import { localDate, dateLabel, hour } from "../meetings/dates";
import { refreshSchedule } from "./refresh";

export function CreateMeeting({ date }: { date: string }) {
  const client = useQueryClient();
  const settings = useQuery({
    queryKey: ["admin-schedule"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/schedule")),
  });
  const [day, setDay] = useState(date);
  const [time, setTime] = useState("18:00");
  const [duration, setDuration] = useState(120);
  const [venue, setVenue] = useState("I LO w Gdańsku");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [confirm, setConfirm] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!settings.data) return;
    if (!confirm) {
      setConfirm(true);
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const item = unwrap(
        await api.POST("/api/v1/admin/meetings", {
          body: {
            expected_version: settings.data.version,
            local_date: day,
            local_time: time,
            duration_minutes: duration,
            venue,
          },
        }),
      );
      setConfirm(false);
      setNotice(
        `Dodano spotkanie: ${dateLabel(item.starts_at)}, ${hour(item.starts_at)}.`,
      );
      await refreshSchedule(client);
    } catch (error) {
      setNotice(message(error));
      setConfirm(false);
      await refreshSchedule(client);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card">
      <h2>Dodaj pojedyncze spotkanie</h2>
      <p className="form-note">
        Dodatkowy termin nie zmienia cotygodniowej serii. Aby przenieść
        istniejące spotkanie, otwórz je w kalendarzu i wybierz „Zmień ten
        termin”.
      </p>
      <form
        onSubmit={(event) => void submit(event)}
        onChange={() => {
          setConfirm(false);
          setNotice("");
        }}
      >
        <fieldset disabled={busy}>
          <div className="form-row">
            <label className="form-field">
              Data spotkania
              <input
                type="date"
                min={localDate(new Date().toISOString())}
                max="9997-12-31"
                required
                value={day}
                onChange={(e) => setDay(e.target.value)}
              />
            </label>
            <label className="form-field">
              Godzina spotkania
              <input
                type="time"
                required
                value={time}
                onChange={(e) => setTime(e.target.value)}
              />
            </label>
          </div>
          <div className="form-row">
            <label className="form-field">
              Czas spotkania (minuty)
              <input
                type="number"
                min={1}
                max={1440}
                required
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
              />
            </label>
            <label className="form-field">
              Miejsce spotkania
              <input
                required
                maxLength={160}
                value={venue}
                onChange={(e) => setVenue(e.target.value)}
              />
            </label>
          </div>
          {confirm && (
            <p role="status">
              Nowe spotkanie: {day.split("-").reverse().join(".")}, {time} ·{" "}
              {duration} min · {venue}. Pozostałe terminy bez zmian.
            </p>
          )}
          <div className="row-actions">
            <button
              className="button primary"
              disabled={!settings.data || settings.isError}
            >
              {confirm
                ? "Zatwierdź dodanie spotkania"
                : "Pokaż podgląd spotkania"}
            </button>
            {confirm && (
              <button
                className="button"
                type="button"
                onClick={() => setConfirm(false)}
              >
                Wróć do edycji
              </button>
            )}
          </div>
        </fieldset>
      </form>
      {settings.isPending && <p role="status">Wczytujemy kalendarz…</p>}
      {settings.isError && (
        <p role="alert">
          Nie udało się pobrać kalendarza.{" "}
          <button className="button" onClick={() => void settings.refetch()}>
            Ponów
          </button>
        </p>
      )}
      <p className="form-notice" role="status">
        {notice}
      </p>
    </section>
  );
}
