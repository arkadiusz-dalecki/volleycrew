import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Trophy } from "lucide-react";
import { api, unwrap } from "../../lib/api/client";
import { dateLabel } from "../meetings/dates";
import { points, delta, rankedMeetings } from "./format";

export function RankingPage() {
  const [params, setParams] = useSearchParams();
  const history = params.get("tab") === "history";
  const [rankingOffset, setRankingOffset] = useState(0),
    [resultOffset, setResultOffset] = useState(0);
  const ranking = useQuery({
    queryKey: ["ranking", rankingOffset],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/ranking", {
          params: { query: { limit: 20, offset: rankingOffset } },
          signal,
        }),
      ),
    enabled: !history,
    refetchInterval: 30_000,
  });
  const results = useQuery({
    queryKey: ["results", resultOffset],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/results", {
          params: { query: { limit: 20, offset: resultOffset } },
          signal,
        }),
      ),
    enabled: history,
    refetchInterval: 30_000,
  });
  const current = history ? results : ranking;
  return (
    <>
      <div className="page-heading">
        <h1>Ranking ekipy</h1>
        <p>Gramy dla przyjemności. Odrobina rywalizacji dodaje smaku.</p>
      </div>
      <div className="ranking-tabs" role="group" aria-label="Widok rankingu">
        <button
          className="button"
          aria-pressed={!history}
          onClick={() => setParams({})}
        >
          Punkty zawodników
        </button>
        <button
          className="button"
          aria-pressed={history}
          onClick={() => setParams({ tab: "history" })}
        >
          Historia spotkań
        </button>
      </div>
      <section className="card ranking-card">
        <div className="section-title">
          <h2>{history ? "Rozegrane spotkania" : "Punkty zawodników"}</h2>
          <Trophy size={21} />
        </div>
        {current.isPending ? (
          <p role="status">Wczytujemy {history ? "spotkania" : "ranking"}…</p>
        ) : current.isError ? (
          <>
            <p role="alert" className="form-error">
              Nie udało się pobrać aktualnych danych.
            </p>
            <button className="button" onClick={() => void current.refetch()}>
              Ponów
            </button>
          </>
        ) : history && results.data ? (
          <>
            {results.data.items.length ? (
              <ol className="result-history-list">
                {results.data.items.map((r) => (
                  <li key={r.meeting_id}>
                    <Link to={`/meetings/${r.meeting_id}`}>
                      <div>
                        <strong>{dateLabel(r.starts_at)}</strong>
                        <small>
                          {r.state === "no_sets"
                            ? "Bez rozegranych setów"
                            : `A ${delta(r.delta_a)} · B ${delta(r.delta_b)} na osobę`}
                          {r.revision > 1 ? ` · wersja ${r.revision}` : ""}
                        </small>
                      </div>
                      <strong className="result-history-score">
                        {r.sets_a}:{r.sets_b}
                      </strong>
                    </Link>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="form-note">Nie ma jeszcze zapisanych wyników.</p>
            )}
            <div className="room-actions">
              {resultOffset > 0 && (
                <button
                  className="button"
                  onClick={() =>
                    setResultOffset(Math.max(0, resultOffset - 20))
                  }
                >
                  Nowsze spotkania
                </button>
              )}
              {results.data.next_offset !== null && (
                <button
                  className="button"
                  onClick={() => setResultOffset(results.data.next_offset!)}
                >
                  Starsze spotkania
                </button>
              )}
            </div>
          </>
        ) : ranking.data ? (
          <>
            <p className="form-note">
              Start: 1000 punktów. Zmiana zależy od proporcji wygranych setów i
              siły drużyn. Bez kar za nieobecność w rankingu.
            </p>
            <ol className="ranking-list">
              {ranking.data.items.map((row) => (
                <li key={row.player.id}>
                  <span className={`ranking-position place-${row.position}`}>
                    {row.position}
                  </span>
                  <Link to={`/ranking/players/${row.player.id}`}>
                    <strong>
                      {row.player.first_name} {row.player.last_name}
                    </strong>
                    {row.player.nickname && (
                      <small>{row.player.nickname}</small>
                    )}
                    <small>
                      {row.meetings
                        ? rankedMeetings(row.meetings)
                        : "Jeszcze bez meczu rankingowego"}
                    </small>
                  </Link>
                  <strong className="ranking-points">
                    {points(row.points)}
                    <small>pkt</small>
                  </strong>
                </li>
              ))}
            </ol>
            <div className="room-actions">
              {rankingOffset > 0 && (
                <button
                  className="button"
                  onClick={() =>
                    setRankingOffset(Math.max(0, rankingOffset - 20))
                  }
                >
                  Poprzednia strona
                </button>
              )}
              {ranking.data.next_offset !== null && (
                <button
                  className="button"
                  onClick={() => setRankingOffset(ranking.data.next_offset!)}
                >
                  Następna strona
                </button>
              )}
            </div>
          </>
        ) : null}
      </section>
    </>
  );
}

export function RatingHistoryPage() {
  const { playerId } = useParams();
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["rating-history", playerId, offset],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/players/{player_id}/rating-history", {
          params: {
            path: { player_id: playerId! },
            query: { offset, limit: 20 },
          },
          signal,
        }),
      ),
    enabled: !!playerId,
    refetchInterval: 30_000,
  });
  return (
    <>
      <Link className="text-link back-link" to="/ranking">
        <ArrowLeft size={16} /> Wróć do rankingu
      </Link>
      <div className="page-heading">
        <h1>Historia punktów</h1>
        <p>
          {query.data
            ? `${query.data.player.first_name} ${query.data.player.last_name} · ${points(query.data.points)} pkt`
            : "Zmiany ELO po spotkaniach."}
        </p>
      </div>
      <section className="card">
        {query.isPending ? (
          <p role="status">Wczytujemy historię punktów…</p>
        ) : query.isError ? (
          <>
            <p role="alert" className="form-error">
              Nie udało się pobrać historii punktów.
            </p>
            <button className="button" onClick={() => void query.refetch()}>
              Ponów
            </button>
          </>
        ) : (
          <>
            {query.data.items.length ? (
              <ol className="rating-history-list">
                {query.data.items.map((r) => (
                  <li key={r.meeting_id}>
                    <div>
                      <Link
                        className="text-link"
                        to={`/meetings/${r.meeting_id}`}
                      >
                        {dateLabel(r.starts_at)} · {r.sets_a}:{r.sets_b}
                      </Link>
                      <p>
                        Drużyna {r.side} · wersja wyniku {r.revision}
                      </p>
                    </div>
                    <div>
                      <strong
                        className={`rating-delta ${Number(r.delta) < 0 ? "negative" : ""}`}
                      >
                        {delta(r.delta)}
                      </strong>
                      <small>
                        {points(r.before)} → {points(r.after)}
                      </small>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="form-note">
                Nie ma jeszcze meczów zmieniających punkty tego zawodnika.
              </p>
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
              {query.data.next_offset !== null && (
                <button
                  className="button"
                  onClick={() => setOffset(query.data.next_offset!)}
                >
                  Starsze wpisy
                </button>
              )}
            </div>
            <p className="form-note">
              Historia pokazuje aktualne przeliczenie po korektach wyników.
              Spotkania bez rozegranych setów nie zmieniają ELO.
            </p>
          </>
        )}
      </section>
    </>
  );
}
