import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { dateLabel, hour } from "../meetings/dates";
import { delta, points } from "./format";
export type Result = components["schemas"]["ResultView"];
export function ResultSummary({ result }: { result: Result }) {
  return (
    <div className="result-summary">
      <div
        className="result-score"
        aria-label={`Wynik ${result.sets_a} do ${result.sets_b}`}
      >
        <span>Drużyna A</span>
        <strong>
          {result.sets_a} : {result.sets_b}
        </strong>
        <span>Drużyna B</span>
      </div>
      {result.state === "no_sets" ? (
        <p className="form-note">
          Bez rozegranych setów. Obecność zachowana, bez punktów ELO za to
          spotkanie.
        </p>
      ) : (
        <>
          <div className="result-deltas">
            <span>
              A <strong>{delta(result.outcome.delta_a)}</strong>
            </span>
            <span>
              B <strong>{delta(result.outcome.delta_b)}</strong>
            </span>
          </div>
          <p className="form-note">
            Zmiana dla każdej osoby w drużynie, również rotującej. Średnie przed
            meczem: A {points(result.outcome.mean_a)} · B{" "}
            {points(result.outcome.mean_b)}.
          </p>
        </>
      )}
      <details className="result-revisions">
        <summary>Historia wyniku ({result.revisions.length})</summary>
        <ol>
          {result.revisions.map((r) => (
            <li key={r.revision}>
              <strong>
                {r.sets_a}:{r.sets_b}
              </strong>{" "}
              · wersja {r.revision} · {r.actor.first_name} {r.actor.last_name}
              <small>
                {dateLabel(r.created_at)}, {hour(r.created_at)}
              </small>
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}
export function ResultCard({ meetingId }: { meetingId: string }) {
  const query = useQuery({
    queryKey: ["result", meetingId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/meetings/{meeting_id}/result", {
          params: { path: { meeting_id: meetingId } },
          signal,
        }),
      ),
    refetchInterval: 30_000,
  });
  if (query.isPending)
    return (
      <section className="card" role="status">
        Wczytujemy wynik…
      </section>
    );
  if (query.isError)
    return (
      <section className="card">
        <p role="alert">Nie udało się pobrać wyniku.</p>
        <button className="button" onClick={() => void query.refetch()}>
          Ponów
        </button>
      </section>
    );
  return query.data ? (
    <section className="card">
      <h2>Wynik spotkania</h2>
      <ResultSummary result={query.data} />
      <Link className="text-link" to="/ranking">
        Zobacz ranking i historię punktów
      </Link>
    </section>
  ) : null;
}
