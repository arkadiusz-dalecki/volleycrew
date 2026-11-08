import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays } from "lucide-react";
import { api, message, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { dateLabel, hour, localDate } from "../meetings/dates";
import { refreshSchedule } from "./refresh";

type Settings = components["schemas"]["ScheduleSettings"];
const weekdays = [
  "Poniedziałek",
  "Wtorek",
  "Środa",
  "Czwartek",
  "Piątek",
  "Sobota",
  "Niedziela",
];
function nextMonday() {
  const today = localDate(new Date().toISOString());
  const date = new Date(`${today}T12:00:00Z`);
  const delta = (8 - date.getUTCDay()) % 7 || 7;
  date.setUTCDate(date.getUTCDate() + delta);
  return date.toISOString().slice(0, 10);
}

function ScheduleForm({ settings }: { settings: Settings }) {
  const today = localDate(new Date().toISOString());
  const current =
    settings.rules.find(
      (rule) =>
        rule.effective_from <= today &&
        (!rule.effective_until || rule.effective_until > today),
    ) ?? settings.rules.at(-1);
  const [from, setFrom] = useState(nextMonday);
  const [weekday, setWeekday] = useState(current?.weekday ?? 1);
  const [time, setTime] = useState(current?.local_time.slice(0, 5) ?? "18:00");
  const [duration, setDuration] = useState(current?.duration_minutes ?? 120);
  const [venue, setVenue] = useState(current?.venue ?? "I LO w Gdańsku");
  const [preview, setPreview] = useState<
    components["schemas"]["SchedulePreview"] | null
  >(null);
  const [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const client = useQueryClient();
  const body = {
    expected_version: settings.version,
    effective_from: from,
    weekday,
    local_time: time,
    duration_minutes: duration,
    venue,
  };
  function edit() {
    setPreview(null);
    setNotice("");
  }
  async function show(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    try {
      setPreview(
        unwrap(await api.POST("/api/v1/admin/schedule/preview", { body })),
      );
    } catch (e) {
      setNotice(message(e));
      setPreview(null);
      await client.invalidateQueries({ queryKey: ["admin-schedule"] });
    } finally {
      setBusy(false);
    }
  }
  async function apply() {
    if (!preview) return;
    setBusy(true);
    setNotice("");
    try {
      unwrap(
        await api.POST("/api/v1/admin/schedule/versions", {
          body: { ...body, preview_token: preview.preview_token },
        }),
      );
      setPreview(null);
      await refreshSchedule(client);
      setNotice(
        "Harmonogram zapisany. Poinformuj grupę na Messengerze o zmianie i nowych potwierdzeniach.",
      );
    } catch (e) {
      setNotice(message(e));
      setPreview(null);
      await refreshSchedule(client);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <form onSubmit={(event) => void show(event)}>
        <div className="form-row">
          <label className="form-field">
            Zmiana od dnia
            <input
              type="date"
              value={from}
              min={today}
              onChange={(e) => {
                edit();
                setFrom(e.target.value);
              }}
              required
              disabled={busy}
            />
          </label>
          <label className="form-field">
            Dzień tygodnia
            <select
              value={weekday}
              onChange={(e) => {
                edit();
                setWeekday(Number(e.target.value));
              }}
              disabled={busy}
            >
              {weekdays.map((name, index) => (
                <option key={name} value={index}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="form-row">
          <label className="form-field">
            Godzina rozpoczęcia
            <input
              type="time"
              value={time}
              onChange={(e) => {
                edit();
                setTime(e.target.value);
              }}
              required
              disabled={busy}
            />
          </label>
          <label className="form-field">
            Czas gry (minuty)
            <input
              type="number"
              min={1}
              max={1440}
              value={duration}
              onChange={(e) => {
                edit();
                setDuration(Number(e.target.value));
              }}
              required
              disabled={busy}
            />
          </label>
        </div>
        <label className="form-field">
          Miejsce
          <input
            value={venue}
            maxLength={160}
            onChange={(e) => {
              edit();
              setVenue(e.target.value);
            }}
            required
            disabled={busy}
          />
        </label>
        <button className="button" disabled={busy}>
          Pokaż podgląd harmonogramu
        </button>
      </form>
      {preview && (
        <div
          className="schedule-preview"
          role="region"
          aria-label="Podgląd harmonogramu"
        >
          <h3>Sprawdź zakres zmiany</h3>
          <p>
            {preview.existing.length} istniejących spotkań ·{" "}
            {preview.reconfirmation_count} zgłoszeń wymaga nowego potwierdzenia
            · {preview.kept_exception_count} zachowanych wyjątków.
          </p>
          <p className="form-note">
            Zmiana dotyczy także kolejnych, jeszcze nieotwartych terminów.
            Zastępuje zaplanowane reguły od wybranej daty. Odwołane pozostają
            odwołane; indywidualne terminy pozostają bez zmian.
          </p>
          <ul className="schedule-change-list">
            {preview.existing.map((item) => (
              <li key={item.id}>
                <span>
                  {dateLabel(item.previous_starts_at)},{" "}
                  {hour(item.previous_starts_at)}
                </span>
                <strong>
                  {item.kept_exception
                    ? "Wyjątek — termin bez zmian"
                    : `→ ${dateLabel(item.starts_at)}, ${hour(item.starts_at)}`}
                </strong>
                {item.status === "cancelled" && (
                  <small>Pozostaje odwołane</small>
                )}
              </li>
            ))}
          </ul>
          <h3>Przykładowe terminy nowej reguły</h3>
          <ul className="schedule-examples">
            {preview.examples.slice(0, 4).map((value) => (
              <li key={value}>
                {dateLabel(value)}, {hour(value)}
              </li>
            ))}
          </ul>
          <p className="form-note">
            Dotychczasowe miejsca czekają na potwierdzenie bez limitu czasu.
            Propozycje z rezerwy wymagają ponownej akceptacji nowego terminu.
          </p>
          <div className="participation-actions">
            <button
              className="button"
              disabled={busy}
              onClick={() => setPreview(null)}
            >
              Wróć do edycji
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => void apply()}
            >
              Zatwierdź harmonogram
            </button>
          </div>
        </div>
      )}
      <p className="form-notice" role="status">
        {notice}
      </p>
      <details className="scheduled-rules">
        <summary>Obowiązujące i zaplanowane reguły</summary>
        <ul>
          {settings.rules.map((rule) => (
            <li key={rule.id}>
              {rule.effective_from} – {rule.effective_until ?? "bez końca"}:{" "}
              {weekdays[rule.weekday]}, {rule.local_time.slice(0, 5)} ·{" "}
              {rule.duration_minutes} min
            </li>
          ))}
        </ul>
      </details>
    </>
  );
}
export function ScheduleEditor() {
  const settings = useQuery({
    queryKey: ["admin-schedule"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/schedule")),
  });
  return (
    <section className="card">
      <div className="section-title">
        <h2>Harmonogram spotkań</h2>
        <CalendarDays size={20} />
      </div>
      <p className="form-note">
        Zmień stały dzień lub godzinę od wybranej daty. Przed zapisem zobaczysz
        dotknięte spotkania.
      </p>
      {settings.isPending ? (
        <p role="status">Wczytujemy harmonogram…</p>
      ) : settings.isError && !settings.data ? (
        <div role="alert">
          <p>Nie udało się pobrać harmonogramu.</p>
          <button className="button" onClick={() => void settings.refetch()}>
            Ponów
          </button>
        </div>
      ) : (
        <>
          {settings.isError && (
            <p role="status" className="connection-notice">
              Nie udało się odświeżyć harmonogramu. Pokazujemy ostatnio pobrane
              dane.
            </p>
          )}
          <ScheduleForm settings={settings.data!} />
        </>
      )}
    </section>
  );
}
