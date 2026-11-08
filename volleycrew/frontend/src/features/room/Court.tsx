import { useQuery } from "@tanstack/react-query";
import { ArrowLeftRight, RotateCw } from "lucide-react";
import { api, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
export type Teams = components["schemas"]["TeamsView"];
export type TeamPlayer = components["schemas"]["TeamPlayer"];
const fullName = (p: TeamPlayer) =>
  `${p.player.first_name} ${p.player.last_name}`;

export function Court({
  teams,
  selected,
  onSelect,
  disabled = false,
  showRatings = true,
}: {
  teams: Teams;
  selected?: string;
  onSelect?: (id: string) => void;
  disabled?: boolean;
  showRatings?: boolean;
}) {
  function playerCard(p: TeamPlayer) {
    const content = (
      <>
        <span className="court-avatar" aria-hidden="true">
          {p.player.first_name[0]}
          {p.player.last_name[0]}
        </span>
        <span className="court-player-name">
          {fullName(p)}{" "}
          {p.player.nickname && <small>{p.player.nickname}</small>}
        </span>
        {onSelect && <ArrowLeftRight size={14} aria-hidden="true" />}
      </>
    );
    return onSelect ? (
      <button
        key={p.player.id}
        className="court-player"
        aria-pressed={selected === p.player.id}
        disabled={disabled}
        onClick={() => onSelect(p.player.id)}
      >
        <span className="sr-only">Zamień: </span>
        {content}
      </button>
    ) : (
      <div key={p.player.id} className="court-player">
        {content}
      </div>
    );
  }
  const sides = [teams.team_a, teams.team_b];
  return (
    <div className="team-court" aria-label="Składy na boisku">
      <div className="court-summary">
        {sides.map((players, i) => (
          <div key={i} className={`court-team-summary side-${i}`}>
            <span className="court-team-letter">{i ? "B" : "A"}</span>
            <div>
              <h3>Drużyna {i ? "B" : "A"}</h3>
              <p>
                {players.length} osób{" "}
                {showRatings && (
                  <>
                    · średnia{" "}
                    {new Intl.NumberFormat("pl-PL", {
                      maximumFractionDigits: 1,
                    }).format(i ? teams.average_b : teams.average_a)}
                  </>
                )}
              </p>
            </div>
          </div>
        ))}
      </div>
      <div className="court-surface">
        {sides.map((players, i) => (
          <div
            key={i}
            className={`court-half side-${i}`}
            aria-label={`Boisko drużyny ${i ? "B" : "A"}`}
          >
            <div className="court-lines" aria-hidden="true" />
            <div className="court-formation">
              {Array.from({ length: 6 }, (_, position) =>
                players[position] ? (
                  playerCard(players[position])
                ) : (
                  <div
                    className="court-empty"
                    key={`empty-${position}`}
                    aria-hidden="true"
                  >
                    <span>·</span>
                  </div>
                ),
              )}
            </div>
          </div>
        ))}
        <div className="court-net" aria-hidden="true">
          <span>SIATKA</span>
        </div>
      </div>
      {sides.some((p) => p.length > 6) && (
        <div className="court-rotation">
          <h3>
            <RotateCw size={16} /> Rotacja w drużynie
          </h3>
          <p>Siódma osoba zmienia się z pozostałymi podczas gry.</p>
          <div className="court-rotation-teams">
            {sides.map((players, i) => (
              <div key={i} className={`rotation-side side-${i}`}>
                <small>Drużyna {i ? "B" : "A"}</small>
                {players[6] ? (
                  playerCard(players[6])
                ) : (
                  <p className="form-note">Bez dodatkowej osoby</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      <p className="form-note court-caption">
        Rozmieszczenie pokazuje skład drużyn. Pozycje i przebieg rotacji
        ustalacie na sali.
      </p>
    </div>
  );
}
export function ConfirmedCourt({ meetingId }: { meetingId: string }) {
  const query = useQuery({
    queryKey: ["public-teams", meetingId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/meetings/{meeting_id}/teams", {
          params: { path: { meeting_id: meetingId } },
          signal,
        }),
      ),
    refetchInterval: 30_000,
  });
  if (query.isPending)
    return (
      <section className="card" role="status">
        Wczytujemy składy…
      </section>
    );
  if (query.isError)
    return (
      <section className="card">
        <p role="alert">Nie udało się wczytać składów.</p>
        <button className="button" onClick={() => void query.refetch()}>
          Ponów
        </button>
      </section>
    );
  return query.data ? (
    <section className="card">
      <div className="section-title">
        <h2>Zatwierdzone drużyny</h2>
        <span className="meeting-state teams_confirmed">Gotowi do gry</span>
      </div>
      <Court teams={query.data} />
    </section>
  ) : null;
}
