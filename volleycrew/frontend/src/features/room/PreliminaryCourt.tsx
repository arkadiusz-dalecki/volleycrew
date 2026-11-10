import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Scale, Shuffle } from "lucide-react";
import { api, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { useAdminView } from "../auth/ViewMode";
import { Court } from "./Court";
import { useRoomAction } from "./useRoomAction";

type Preview = components["schemas"]["PreliminaryTeamsView"];
type Meeting = components["schemas"]["MeetingSummary"];
export function PreliminaryCourt({ meeting }: { meeting: Meeting }) {
  const query = useQuery({
    queryKey: ["preliminary-teams", meeting.id],
    enabled: meeting.persisted,
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/meetings/{meeting_id}/preliminary-teams", {
          params: { path: { meeting_id: meeting.id } },
          signal,
        }),
      ),
    refetchInterval: 30_000,
  });
  const admin = useAdminView();
  const action = useRoomAction();
  const [selected, setSelected] = useState<{
    id: string;
    token: string;
    revision: number;
  } | null>(null);
  const current = query.data;
  const selectedId =
    current &&
    selected?.token === current.roster_token &&
    selected.revision === current.revision
      ? selected.id
      : undefined;
  function save(
    mode: "balanced" | "random" | "manual",
    a?: Preview["team_a"],
    b?: Preview["team_b"],
  ) {
    if (!current) return;
    void action.run(
      async () =>
        unwrap(
          await api.PUT(
            "/api/v1/admin/meetings/{meeting_id}/preliminary-teams",
            {
              params: { path: { meeting_id: meeting.id } },
              body: {
                roster_token: current.roster_token,
                revision: current.revision,
                mode,
                team_a: (a ?? []).map((p) => p.player.id),
                team_b: (b ?? []).map((p) => p.player.id),
              },
            },
          ),
        ),
      () => setSelected(null),
    );
  }
  function select(id: string) {
    if (!current) return;
    const a = [...current.team_a],
      b = [...current.team_b];
    const fromA = a.findIndex((p) => p.player.id === selectedId),
      fromB = b.findIndex((p) => p.player.id === selectedId);
    const nextA = a.findIndex((p) => p.player.id === id),
      nextB = b.findIndex((p) => p.player.id === id);
    if (fromA >= 0 && nextB >= 0) {
      [a[fromA], b[nextB]] = [b[nextB], a[fromA]];
      save("manual", a, b);
    } else if (fromB >= 0 && nextA >= 0) {
      [b[fromB], a[nextA]] = [a[nextA], b[fromB]];
      save("manual", a, b);
    } else
      setSelected(
        id === selectedId
          ? null
          : { id, token: current.roster_token, revision: current.revision },
      );
  }
  function transfer() {
    if (!current || !selectedId) return;
    const a = [...current.team_a],
      b = [...current.team_b];
    const inA = a.findIndex((p) => p.player.id === selectedId),
      inB = b.findIndex((p) => p.player.id === selectedId);
    if (inA >= 0 && a.length > b.length) b.push(...a.splice(inA, 1));
    else if (inB >= 0 && b.length > a.length) a.push(...b.splice(inB, 1));
    else return;
    save("manual", a, b);
  }
  if (meeting.persisted && !query.isPending && !current && !query.isError)
    return null;
  const canTransfer =
    !!current &&
    !!selectedId &&
    ((current.team_a.length > current.team_b.length &&
      current.team_a.some((p) => p.player.id === selectedId)) ||
      (current.team_b.length > current.team_a.length &&
        current.team_b.some((p) => p.player.id === selectedId)));
  return (
    <section className="card preliminary-court" aria-label="Wstępne drużyny">
      <div className="section-title">
        <h2>Wstępne drużyny</h2>
        <span className="meeting-state scheduled">Z zapisów</span>
      </div>
      <p className="form-note">
        Podział z osób z potwierdzonym miejscem. Obecność nie jest jeszcze
        sprawdzona. Zmiana zapisanych osób przywraca aktualny podział według
        ELO.
      </p>
      {query.isPending && meeting.persisted ? (
        <p role="status">Przygotowujemy boisko…</p>
      ) : !current && query.isError ? (
        <p role="alert">
          Nie udało się pobrać wstępnych drużyn.{" "}
          <button className="button" onClick={() => void query.refetch()}>
            Ponów
          </button>
        </p>
      ) : !current || current.participant_count < 2 ? (
        <p className="form-note">
          Do pokazania boiska potrzeba co najmniej 2 osób z potwierdzonym
          miejscem.
        </p>
      ) : (
        <>
          {query.isError && (
            <p role="alert" className="connection-notice">
              Nie udało się odświeżyć boiska. Pokazujemy ostatni podział.{" "}
              <button className="button" onClick={() => void query.refetch()}>
                Ponów
              </button>
            </p>
          )}
          <p className="form-note">
            {current.method === "balanced"
              ? "Wyrównane według ELO"
              : current.method === "random"
                ? "Losowanie administratora"
                : "Ręczny podział administratora"}{" "}
            · {current.participant_count} osób
          </p>
          {admin && (
            <>
              <div className="room-actions">
                <button
                  className="button"
                  disabled={action.busy || action.canRetry || query.isError}
                  onClick={() => save("balanced")}
                >
                  <Scale size={16} />
                  Według ELO
                </button>
                <button
                  className="button"
                  disabled={action.busy || action.canRetry || query.isError}
                  onClick={() => save("random")}
                >
                  <Shuffle size={16} />
                  Losuj wstępne składy
                </button>
              </div>
              <p className="form-note">
                Dotknij osoby, a potem osoby z drugiej drużyny, aby je zamienić.
                Zmiany zapisują się dla całej ekipy. Po sprawdzeniu obecności
                wybierz „Użyj wstępnego podziału” w kroku Drużyny.
              </p>
            </>
          )}
          <Court
            teams={current}
            selected={selectedId}
            onSelect={admin ? select : undefined}
            disabled={action.busy || action.canRetry || query.isError}
          />
          {admin && canTransfer && (
            <button
              className="button"
              disabled={action.busy || action.canRetry || query.isError}
              onClick={transfer}
            >
              Przenieś do mniejszej drużyny
            </button>
          )}
        </>
      )}
      {action.error && (
        <p role="alert" className="form-error">
          {action.error}
        </p>
      )}
      {action.canRetry && (
        <button
          className="button"
          disabled={action.busy}
          onClick={() => void action.retry()}
        >
          Ponów zapis podziału
        </button>
      )}
    </section>
  );
}
