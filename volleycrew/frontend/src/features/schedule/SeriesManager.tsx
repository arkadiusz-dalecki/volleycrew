import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { api, message, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { localDate } from "../meetings/dates";
import { ScheduleEditor } from "./ScheduleEditor";
import { refreshSchedule } from "./refresh";

const weekdays = [
  "poniedziałek",
  "wtorek",
  "środa",
  "czwartek",
  "piątek",
  "sobota",
  "niedziela",
];
export function SeriesManager() {
  const client = useQueryClient();
  const settings = useQuery({
    queryKey: ["admin-schedule"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/schedule")),
  });
  const [editing, setEditing] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<{
    id: string;
    preview: components["schemas"]["SeriesChangePreview"];
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const today = localDate(new Date().toISOString());
  const rules =
    settings.data?.rules.filter(
      (rule) => !rule.effective_until || rule.effective_until > today,
    ) ?? [];
  async function prepare(id: string) {
    if (!settings.data) return;
    setBusy(true);
    setNotice("");
    try {
      const preview = unwrap(
        await api.POST(
          "/api/v1/admin/schedule/rules/{rule_id}/delete-preview",
          {
            params: { path: { rule_id: id } },
            body: { expected_version: settings.data.version },
          },
        ),
      );
      setDeleting({ id, preview });
    } catch (error) {
      setNotice(message(error));
      await refreshSchedule(client);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!deleting) return;
    setBusy(true);
    setNotice("");
    try {
      unwrap(
        await api.POST("/api/v1/admin/schedule/rules/{rule_id}/delete", {
          params: { path: { rule_id: deleting.id } },
          body: {
            expected_version: deleting.preview.version,
            preview_token: deleting.preview.preview_token,
          },
        }),
      );
      setDeleting(null);
      setEditing(null);
      setNotice("Seria i jej przyszłe terminy zostały usunięte z kalendarza.");
    } catch (error) {
      setDeleting(null);
      setNotice(message(error));
    } finally {
      await refreshSchedule(client);
      setBusy(false);
    }
  }
  const selected = rules.find((rule) => rule.id === editing);
  return (
    <section className="series-manager" aria-label="Zarządzanie seriami">
      <h2>Twoje serie spotkań</h2>
      {settings.isPending ? (
        <p role="status">Wczytujemy serie…</p>
      ) : settings.isError ? (
        <p role="alert">
          Nie udało się pobrać serii.{" "}
          <button className="button" onClick={() => void settings.refetch()}>
            Ponów
          </button>
        </p>
      ) : !rules.length ? (
        <p className="form-note">Nie ma zaplanowanych serii.</p>
      ) : (
        <ul className="series-list">
          {rules.map((rule) => (
            <li
              className="card"
              key={rule.id}
              data-testid={`series-${rule.id}`}
            >
              <div>
                <h3>
                  Co tydzień: {weekdays[rule.weekday]},{" "}
                  {rule.local_time.slice(0, 5)}
                </h3>
                <p className="form-note">
                  {rule.effective_from <= today
                    ? "Obowiązuje"
                    : `Od ${rule.effective_from.split("-").reverse().join(".")}`}{" "}
                  –{" "}
                  {rule.effective_until
                    ? new Date(
                        Date.parse(`${rule.effective_until}T12:00:00Z`) -
                          86400000,
                      )
                        .toISOString()
                        .slice(0, 10)
                    : "bez końca"}{" "}
                  · {rule.duration_minutes} min · {rule.venue}
                </p>
              </div>
              <div className="row-actions">
                <button
                  className="button"
                  disabled={busy}
                  aria-expanded={editing === rule.id}
                  onClick={() =>
                    setEditing(editing === rule.id ? null : rule.id)
                  }
                >
                  <Pencil size={16} /> Edytuj serię
                </button>
                <button
                  className="button"
                  disabled={busy}
                  onClick={(event) => {
                    event.currentTarget.focus();
                    void prepare(rule.id);
                  }}
                >
                  <Trash2 size={16} /> Usuń serię
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {selected && (
        <ScheduleEditor
          rule={selected}
          onSaved={() => {
            setEditing(null);
            setNotice("Seria została zmieniona.");
          }}
        />
      )}
      {notice && (
        <p className="form-notice" role="status">
          {notice}
        </p>
      )}
      {deleting && (
        <ConfirmDialog
          title="Usunąć serię spotkań?"
          busy={busy}
          onDismiss={() => setDeleting(null)}
        >
          <p>
            Usuniesz wszystkie przyszłe terminy tej serii, także jeszcze
            nieotwarte spotkania. {deleting.preview.removed_count} istniejących
            spotkań zniknie z kalendarza. Zapisy i propozycje zostaną zamknięte
            bez oznaczeń nieobecności.
          </p>
          <p>
            Rozegrane spotkania, inne serie i pojedyncze dodatkowe terminy
            pozostaną.
          </p>
          <div className="row-actions">
            <button
              className="button"
              disabled={busy}
              onClick={() => setDeleting(null)}
            >
              Zachowaj serię
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => void remove()}
            >
              Usuń serię
            </button>
          </div>
        </ConfirmDialog>
      )}
    </section>
  );
}
