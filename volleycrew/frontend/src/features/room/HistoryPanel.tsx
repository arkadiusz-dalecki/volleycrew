import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { dateLabel, hour } from "../meetings/dates";
import { useRoomAction } from "./useRoomAction";
type Item = components["schemas"]["HistoryItem"];
type Kind = components["schemas"]["HistoryItem"]["current_kind"];
const labels: Record<Kind, string> = {
  present: "Obecność",
  no_show: "Nieobecność bez odwołania",
  excused: "Usprawiedliwiona nieobecność",
  normal_cancellation: "Zwykła rezygnacja",
  late_cancellation: "Późna rezygnacja",
  late_offer_exception: "Rezygnacja — wyjątek późnej oferty",
};

function HistoryRow({ item, admin }: { item: Item; admin: boolean }) {
  const [edit, setEdit] = useState(false),
    [reason, setReason] = useState("");
  const [value, setValue] = useState<Kind>(item.current_kind);
  const action = useRoomAction();
  const kinds: Kind[] = [
    "normal_cancellation",
    "late_cancellation",
    "late_offer_exception",
  ].includes(item.original_kind)
    ? [
        "normal_cancellation",
        "late_cancellation",
        "late_offer_exception",
        "excused",
      ]
    : ["present", "no_show", "excused"];
  return (
    <li className="history-entry">
      <div className="section-title">
        <h3>{dateLabel(item.starts_at)}</h3>
        <span className={`history-kind ${item.current_kind}`}>
          {labels[item.current_kind]}
        </span>
      </div>
      <p className="form-note">
        Źródłowy wpis: {labels[item.original_kind]}. {item.actor.first_name}{" "}
        {item.actor.last_name} · {dateLabel(item.created_at)},{" "}
        {hour(item.created_at)}
      </p>
      {item.source_reason && (
        <p className="history-correction">
          Powód uzupełnienia: {item.source_reason}
        </p>
      )}
      {item.corrections.map((c) => (
        <div className="history-correction" key={c.id}>
          <strong>Korekta: {labels[c.kind]}</strong>
          <p>{c.reason}</p>
          <small>
            {c.actor.first_name} {c.actor.last_name} · {dateLabel(c.created_at)}
            , {hour(c.created_at)}
          </small>
        </div>
      ))}
      <Link className="text-link" to={`/meetings/${item.meeting_id}`}>
        Otwórz spotkanie
      </Link>
      {admin && (
        <button className="button small" onClick={() => setEdit(!edit)}>
          {edit ? "Zamknij formularz" : "Popraw wpis historii"}
        </button>
      )}
      {edit && (
        <form
          className="confirmation-panel"
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(
              async (key) =>
                unwrap(
                  await api.POST(
                    "/api/v1/admin/meetings/{meeting_id}/attendance/corrections",
                    {
                      params: {
                        path: { meeting_id: item.meeting_id },
                        header: { "Idempotency-Key": key },
                      },
                      body: {
                        expected_version: item.meeting_version,
                        event_id: item.id,
                        value,
                        reason,
                      },
                    },
                  ),
                ),
              () => {
                setEdit(false);
                setReason("");
              },
            );
          }}
        >
          <label className="form-field">
            Poprawna klasyfikacja
            <select
              value={value}
              onChange={(e) => setValue(e.target.value as Kind)}
            >
              {kinds.map((k) => (
                <option key={k} value={k}>
                  {labels[k]}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            Powód korekty
            <textarea
              required
              maxLength={500}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <p className="form-note">
            Zmiana faktycznej obecności respektuje wolne miejsca i rezerwacje.
            Zatwierdzone składy trzeba najpierw otworzyć do poprawy w spotkaniu.
          </p>
          <button
            className="button primary"
            disabled={action.busy || action.canRetry || !reason.trim()}
          >
            Zapisz korektę historii
          </button>
        </form>
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
          Ponów tę operację
        </button>
      )}
    </li>
  );
}
export function HistoryPanel({ playerId }: { playerId?: string }) {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["attendance-history", playerId ?? "me", offset],
    queryFn: async ({ signal }) =>
      playerId
        ? unwrap(
            await api.GET(
              "/api/v1/admin/players/{player_id}/attendance-history",
              {
                params: {
                  path: { player_id: playerId },
                  query: { limit: 20, offset },
                },
                signal,
              },
            ),
          )
        : unwrap(
            await api.GET("/api/v1/me/attendance-history", {
              params: { query: { limit: 20, offset } },
              signal,
            }),
          ),
    refetchInterval: 30_000,
  });
  return (
    <section className="card history-panel">
      <h2>Prywatna historia obecności</h2>
      <p className="form-note">
        Widoczna tylko dla tego zawodnika i organizatora. Bez automatycznych
        kar.
      </p>
      {query.isPending ? (
        <p role="status">Wczytujemy historię…</p>
      ) : query.isError && !query.data ? (
        <>
          <p role="alert">Nie udało się wczytać historii.</p>
          <button className="button" onClick={() => void query.refetch()}>
            Ponów
          </button>
        </>
      ) : (
        <>
          {query.isError && (
            <p role="status" className="connection-notice">
              Nie udało się odświeżyć historii. Pokazujemy ostatnio pobrane
              dane.
            </p>
          )}
          {query.data!.items.length ? (
            <ol className="history-list">
              {query.data!.items.map((item) => (
                <HistoryRow key={item.id} item={item} admin={!!playerId} />
              ))}
            </ol>
          ) : (
            <p className="form-note">Nie ma jeszcze wpisów w historii.</p>
          )}
          <div className="room-actions">
            {offset > 0 && (
              <button
                className="button"
                onClick={() => setOffset(Math.max(0, offset - 20))}
              >
                Nowsze wpisy
              </button>
            )}
            {query.data!.next_offset !== null && (
              <button
                className="button"
                onClick={() => setOffset(query.data!.next_offset!)}
              >
                Starsze wpisy
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}
export function PlayerHistoryPage() {
  const { playerId } = useParams();
  const players = useQuery({
    queryKey: ["admin-players"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/players")),
  });
  const player = players.data?.find((p) => p.id === playerId);
  return (
    <>
      <Link className="text-link back-link" to="/admin/settings">
        Wróć do ustawień ekipy
      </Link>
      <div className="page-heading">
        <h1>Historia zawodnika</h1>
        <p>
          {player
            ? `${player.first_name} ${player.last_name}`
            : "Historia jest dostępna tylko organizatorowi."}
        </p>
      </div>
      {playerId && <HistoryPanel key={playerId} playerId={playerId} />}
    </>
  );
}
