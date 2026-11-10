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

function ScheduleForm({
  settings,
  rule,
  onSaved,
}: {
  settings: Settings;
  rule?: components["schemas"]["ScheduleView"];
  onSaved?: () => void;
}) {
  const today = localDate(new Date().toISOString());
  const current =
    rule ??
    settings.rules.find(
      (rule) =>
        rule.effective_from <= today &&
        (!rule.effective_until || rule.effective_until > today),
    ) ??
    settings.rules.at(-1);
  const [from, setFrom] = useState(() => {
    if (!rule) return nextMonday();
    const minimum = rule.effective_from > today ? rule.effective_from : today;
    if (
      minimum === today &&
      new Date(`${today}T12:00:00Z`).getUTCDay() === (rule.weekday + 1) % 7 &&
      hour(new Date().toISOString()) >= rule.local_time.slice(0, 5)
    ) {
      return new Date(Date.parse(`${today}T12:00:00Z`) + 86400000)
        .toISOString()
        .slice(0, 10);
    }
    return minimum;
  });
  const [until, setUntil] = useState(() =>
    rule?.effective_until
      ? new Date(Date.parse(`${rule.effective_until}T12:00:00Z`) - 86400000)
          .toISOString()
          .slice(0, 10)
      : "",
  );
  const [weekday, setWeekday] = useState(current?.weekday ?? 1);
  const [time, setTime] = useState(current?.local_time.slice(0, 5) ?? "18:00");
  const [duration, setDuration] = useState(current?.duration_minutes ?? 120);
  const [venue, setVenue] = useState(current?.venue ?? "I LO w Gdańsku");
  const [preview, setPreview] = useState<
    | components["schemas"]["SchedulePreview"]
    | components["schemas"]["SeriesChangePreview"]
    | null
  >(null);
  const [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const client = useQueryClient();
  const body = {
    expected_version: settings.version,
    effective_from: from,
    effective_until: until
      ? new Date(new Date(`${until}T12:00:00Z`).getTime() + 86400000)
          .toISOString()
          .slice(0, 10)
      : null,
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
        rule
          ? unwrap(
              await api.POST("/api/v1/admin/schedule/rules/{rule_id}/preview", {
                params: { path: { rule_id: rule.id } },
                body,
              }),
            )
          : unwrap(await api.POST("/api/v1/admin/schedule/preview", { body })),
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
        rule
          ? await api.POST("/api/v1/admin/schedule/rules/{rule_id}/edit", {
              params: { path: { rule_id: rule.id } },
              body: { ...body, preview_token: preview.preview_token },
            })
          : await api.POST("/api/v1/admin/schedule/versions", {
              body: { ...body, preview_token: preview.preview_token },
            }),
      );
      setPreview(null);
      await refreshSchedule(client);
      onSaved?.();
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
        <label className="form-field">
          Do dnia (włącznie, opcjonalnie)
          <input
            type="date"
            value={until}
            min={from}
            max="9997-12-31"
            disabled={busy}
            onChange={(e) => {
              edit();
              setUntil(e.target.value);
            }}
          />
          <small>
            {rule
              ? "Terminy poza nowym zakresem zostaną usunięte z kalendarza."
              : "Po tej dacie wróci wcześniejszy harmonogram."}{" "}
            Puste pole oznacza serię bez końca.
          </small>
        </label>
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
            <strong>
              {from.split("-").reverse().join(".")} –{" "}
              {until
                ? `${until.split("-").reverse().join(".")} (włącznie)`
                : "bez końca"}{" "}
              · {weekdays[weekday]}, {time} · {duration} min · {venue}
            </strong>
          </p>
          {"existing" in preview ? (
            <>
              <p>
                {preview.existing.filter((item) => !item.deleted).length}{" "}
                istniejących spotkań · {preview.reconfirmation_count} zgłoszeń
                wymaga nowego potwierdzenia · {preview.kept_exception_count}{" "}
                zachowanych wyjątków.
              </p>
              <p className="form-note">
                Zmiana dotyczy także kolejnych, jeszcze nieotwartych terminów.
                Zastępuje zaplanowane reguły w wybranym zakresie. Po końcu serii
                wraca wcześniejszy harmonogram. Odwołane pozostają odwołane;
                indywidualne terminy pozostają bez zmian.
              </p>
              <ul className="schedule-change-list">
                {preview.existing
                  .filter((item) => !item.deleted)
                  .map((item) => (
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
            </>
          ) : (
            <>
              <p>
                {preview.affected_count} istniejących spotkań ·{" "}
                {preview.removed_count} do usunięcia ·{" "}
                {preview.reconfirmation_count} zgłoszeń wymaga nowego
                potwierdzenia · {preview.kept_exception_count} zachowanych
                wyjątków.
              </p>
              <p>
                Nowy zakres zastąpi przyszłą część tej serii. Usunięte wcześniej
                spotkania nie wrócą. Inne serie i dodatkowe spotkania pozostaną
                bez zmian.
              </p>
            </>
          )}
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
    </>
  );
}
export function ScheduleEditor({
  rule,
  onSaved,
}: {
  rule?: components["schemas"]["ScheduleView"];
  onSaved?: () => void;
}) {
  const settings = useQuery({
    queryKey: ["admin-schedule"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/schedule")),
  });
  return (
    <section className="card">
      <div className="section-title">
        <h2>{rule ? "Edytuj serię" : "Seria spotkań"}</h2>
        <CalendarDays size={20} />
      </div>
      <p className="form-note">
        {rule
          ? "Zmień przyszłe terminy tej serii. Skrócenie zakresu usunie wypadające spotkania. Przed zapisem sprawdzisz skutki."
          : "Ustaw cotygodniową grę od–do. Seria zastąpi dotychczasowy harmonogram w tym okresie. Przed zapisem zobaczysz dotknięte spotkania."}
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
          <ScheduleForm
            key={rule?.id ?? "new"}
            settings={settings.data!}
            rule={rule}
            onSaved={onSaved}
          />
        </>
      )}
    </section>
  );
}
