import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { useRoomAction } from "../room/useRoomAction";
import { Court, type Teams, type TeamPlayer } from "../room/Court";
import { ResultSummary } from "./ResultCard";
import { delta, points } from "./format";
type AdminResult = components["schemas"]["AdminResultView"];
type Preview = components["schemas"]["ResultPreview"];
type PresenceChange = components["schemas"]["PresenceCorrection"];

export function ResultEditor({
  meetingId,
  version,
}: {
  meetingId: string;
  version: number;
}) {
  const result = useQuery({
    queryKey: ["admin-result", meetingId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/admin/meetings/{meeting_id}/result", {
          params: { path: { meeting_id: meetingId } },
          signal,
        }),
      ),
    refetchInterval: 30_000,
  });
  const teams = useQuery({
    queryKey: ["room-teams", meetingId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/admin/meetings/{meeting_id}/teams", {
          params: { path: { meeting_id: meetingId } },
          signal,
        }),
      ),
  });
  if (result.isPending || teams.isPending)
    return <p role="status">Wczytujemy formularz wyniku…</p>;
  if (
    (result.isError && result.data === undefined) ||
    (teams.isError && teams.data === undefined)
  )
    return (
      <>
        <p className="form-error" role="alert">
          Nie udało się pobrać wyniku lub składów.
        </p>
        <button
          className="button"
          onClick={() => {
            void result.refetch();
            void teams.refetch();
          }}
        >
          Ponów
        </button>
      </>
    );
  return (
    <>
      {(result.isError || teams.isError) && (
        <p role="status" className="connection-notice">
          Nie udało się odświeżyć wyniku. Pokazujemy ostatnio pobrane dane;
          niezapisane zmiany pozostają w formularzu.
        </p>
      )}
      {teams.data ? (
        <Editor
          meetingId={meetingId}
          version={version}
          saved={result.data ?? null}
          teams={teams.data}
        />
      ) : (
        <p className="form-note">Zatwierdź składy przed wpisaniem wyniku.</p>
      )}
    </>
  );
}

function Editor({
  meetingId,
  version,
  saved,
  teams,
}: {
  meetingId: string;
  version: number;
  saved: AdminResult | null;
  teams: Teams;
}) {
  const action = useRoomAction();
  const hintId = useId();
  const [editing, setEditing] = useState(false),
    [aScore, setAScore] = useState(""),
    [bScore, setBScore] = useState("");
  const [baseVersion, setBaseVersion] = useState(version),
    [reason, setReason] = useState("");
  const [roster, setRoster] = useState<{
    a: TeamPlayer[];
    b: TeamPlayer[];
  } | null>(null);
  const [selected, setSelected] = useState("");
  const [addTo, setAddTo] = useState<"A" | "B">("A"),
    [addId, setAddId] = useState("");
  const [changes, setChanges] = useState<Record<string, PresenceChange>>({});
  const [preview, setPreview] = useState<Preview | null>(null);
  const people = useQuery({
    queryKey: ["admin-players"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/players")),
  });
  const locked = action.busy || action.canRetry;
  const stale = baseVersion !== version;
  const current = {
    a: roster?.a ?? teams.team_a,
    b: roster?.b ?? teams.team_b,
  };
  const original = new Set(
    [...teams.team_a, ...teams.team_b].map((p) => p.player.id),
  );
  const chosen = new Set([...current.a, ...current.b].map((p) => p.player.id));
  function reset(correction = true) {
    setEditing(correction);
    setBaseVersion(version);
    setAScore(saved ? String(saved.sets_a) : "");
    setBScore(saved ? String(saved.sets_b) : "");
    setReason("");
    setRoster(null);
    setChanges({});
    setPreview(null);
    setSelected("");
  }
  function updateRoster(next: typeof current) {
    setRoster(next);
    setPreview(null);
    const nextIds = new Set([...next.a, ...next.b].map((p) => p.player.id));
    const nextChanges: Record<string, PresenceChange> = {};
    for (const id of new Set([...original, ...nextIds]))
      if (original.has(id) !== nextIds.has(id))
        nextChanges[id] = changes[id] ?? {
          player_id: id,
          value: nextIds.has(id) ? "present" : "no_show",
          reason: "",
        };
    setChanges(nextChanges);
  }
  function select(id: string) {
    const a = [...current.a],
      b = [...current.b];
    const fromA = a.findIndex((p) => p.player.id === selected),
      fromB = b.findIndex((p) => p.player.id === selected);
    const toA = a.findIndex((p) => p.player.id === id),
      toB = b.findIndex((p) => p.player.id === id);
    if (fromA >= 0 && toB >= 0) [a[fromA], b[toB]] = [b[toB], a[fromA]];
    else if (fromB >= 0 && toA >= 0) [a[toA], b[fromB]] = [b[fromB], a[toA]];
    else {
      setSelected(selected === id ? "" : id);
      return;
    }
    updateRoster({ a, b });
    setSelected("");
  }
  function remove(id: string) {
    updateRoster({
      a: current.a.filter((p) => p.player.id !== id),
      b: current.b.filter((p) => p.player.id !== id),
    });
    setSelected("");
  }
  function add() {
    const person = people.data?.find((p) => p.id === addId);
    if (!person) return;
    const entry: TeamPlayer = {
      player: {
        id: person.id,
        first_name: person.first_name,
        last_name: person.last_name,
        nickname: person.nickname,
      },
      position: 0,
      rating: 1000,
    };
    updateRoster({
      a: addTo === "A" ? [...current.a, entry] : current.a,
      b: addTo === "B" ? [...current.b, entry] : current.b,
    });
    setAddId("");
  }
  const common = {
    expected_version: baseVersion,
    sets_a: Number(aScore),
    sets_b: Number(bScore),
  };
  const correction = {
    ...common,
    team_a: current.a.map((p) => p.player.id),
    team_b: current.b.map((p) => p.player.id),
    reason,
    presence_changes: Object.values(changes),
  };
  const validScore =
    aScore !== "" &&
    bScore !== "" &&
    Number.isSafeInteger(Number(aScore)) &&
    Number.isSafeInteger(Number(bScore)) &&
    Number(aScore) >= 0 &&
    Number(bScore) >= 0;
  const validRoster =
    current.a.length >= 1 &&
    current.b.length >= 1 &&
    current.a.length <= 7 &&
    current.b.length <= 7 &&
    Math.abs(current.a.length - current.b.length) <= 1;
  const canPreview =
    validScore &&
    !stale &&
    (!saved ||
      (!!reason.trim() &&
        validRoster &&
        Object.values(changes).every((c) => !!c.reason.trim())));
  function showPreview() {
    void action.run(async () => {
      const view = saved
        ? unwrap(
            await api.POST(
              "/api/v1/admin/meetings/{meeting_id}/result-correction-preview",
              { params: { path: { meeting_id: meetingId } }, body: correction },
            ),
          )
        : unwrap(
            await api.POST(
              "/api/v1/admin/meetings/{meeting_id}/result-preview",
              { params: { path: { meeting_id: meetingId } }, body: common },
            ),
          );
      setPreview(view);
    });
  }
  function commit() {
    if (!preview) return;
    const expected_rating_version = preview.rating_version;
    void action.run(
      async (key) =>
        saved
          ? unwrap(
              await api.POST(
                "/api/v1/admin/meetings/{meeting_id}/result/corrections",
                {
                  params: {
                    path: { meeting_id: meetingId },
                    header: { "Idempotency-Key": key },
                  },
                  body: { ...correction, expected_rating_version },
                },
              ),
            )
          : unwrap(
              await api.POST("/api/v1/admin/meetings/{meeting_id}/result", {
                params: {
                  path: { meeting_id: meetingId },
                  header: { "Idempotency-Key": key },
                },
                body: { ...common, expected_rating_version },
              }),
            ),
      () => {
        setPreview(null);
        setEditing(false);
      },
    );
  }
  const court = {
    ...teams,
    team_a: current.a,
    team_b: current.b,
    average_a:
      current.a.reduce((sum, p) => sum + p.rating, 0) / (current.a.length || 1),
    average_b:
      current.b.reduce((sum, p) => sum + p.rating, 0) / (current.b.length || 1),
  };
  return (
    <div className="result-editor">
      {saved && (
        <>
          <ResultSummary result={saved} />
          <details className="result-private-reasons">
            <summary>Powody korekt — tylko organizator</summary>
            {Object.entries(saved.squads).map(([revision, squads]) => (
              <div key={revision}>
                <strong>Wersja {revision}</strong>
                <p>
                  {saved.reasons[Number(revision)] ?? "Pierwszy zapis wyniku"}
                </p>
                <p>
                  A:{" "}
                  {squads.team_a
                    .map((p) => `${p.first_name} ${p.last_name}`)
                    .join(", ")}
                </p>
                <p>
                  B:{" "}
                  {squads.team_b
                    .map((p) => `${p.first_name} ${p.last_name}`)
                    .join(", ")}
                </p>
              </div>
            ))}
          </details>
          {!editing && (
            <button className="button" onClick={() => reset()}>
              Skoryguj wynik lub składy
            </button>
          )}
        </>
      )}
      {(!saved || editing) && (
        <fieldset className="result-form" disabled={locked}>
          <legend>
            {saved ? "Korekta zakończonego spotkania" : "Wynik w setach"}
          </legend>
          <p className="form-note">
            Wpisz łączny wynik spotkania. Podgląd pokaże zmianę punktów przed
            zapisaniem.
          </p>
          {stale && (
            <p className="form-error" role="alert">
              Spotkanie zmieniło się w innej karcie. Twoje pola są zachowane.{" "}
              <button className="button small" onClick={() => reset(!!saved)}>
                Wczytaj aktualny formularz
              </button>
            </p>
          )}
          <div className="result-inputs">
            <label className="form-field">
              Sety drużyny A
              <input
                type="number"
                min="0"
                max="2147483647"
                step="1"
                inputMode="numeric"
                value={aScore}
                onChange={(e) => {
                  setAScore(e.target.value);
                  setPreview(null);
                }}
              />
            </label>
            <span aria-hidden="true">:</span>
            <label className="form-field">
              Sety drużyny B
              <input
                type="number"
                min="0"
                max="2147483647"
                step="1"
                inputMode="numeric"
                value={bScore}
                onChange={(e) => {
                  setBScore(e.target.value);
                  setPreview(null);
                }}
              />
            </label>
          </div>
          {saved && (
            <>
              <label className="form-field">
                Powód korekty wyniku lub składu
                <textarea
                  aria-label="Powód korekty wyniku lub składu"
                  aria-describedby={hintId}
                  maxLength={500}
                  value={reason}
                  onChange={(e) => {
                    setReason(e.target.value);
                    setPreview(null);
                  }}
                  required
                />
                <small id={hintId}>
                  Widoczny tylko organizatorowi. Poprzednie wersje wyniku i
                  składów zostaną zachowane.
                </small>
              </label>
              <details className="historical-team-edit">
                <summary>Popraw historyczny skład i obecność</summary>
                <p className="form-note">
                  Dotknij osób z przeciwnych drużyn, aby je zamienić. Usunięcie
                  lub dodanie osoby wymaga osobnego, prywatnego powodu korekty
                  obecności.
                </p>
                <Court
                  showRatings={false}
                  teams={court}
                  selected={selected}
                  onSelect={select}
                  disabled={locked}
                />
                {selected && (
                  <div className="room-actions">
                    <button className="button" onClick={() => remove(selected)}>
                      Usuń wybraną osobę z obecnych
                    </button>
                    <button
                      className="button"
                      disabled={
                        (current.a.some((p) => p.player.id === selected)
                          ? current.b
                          : current.a
                        ).length >= 7
                      }
                      onClick={() => {
                        const p = [...current.a, ...current.b].find(
                          (p) => p.player.id === selected,
                        )!;
                        updateRoster(
                          current.a.some((p) => p.player.id === selected)
                            ? {
                                a: current.a.filter(
                                  (p) => p.player.id !== selected,
                                ),
                                b: [...current.b, p],
                              }
                            : {
                                a: [...current.a, p],
                                b: current.b.filter(
                                  (p) => p.player.id !== selected,
                                ),
                              },
                        );
                        setSelected("");
                      }}
                    >
                      Przenieś do drugiej drużyny
                    </button>
                  </div>
                )}
                {people.isError ? (
                  <button
                    className="button"
                    onClick={() => void people.refetch()}
                  >
                    Ponów wczytanie profili
                  </button>
                ) : (
                  <div className="historical-add">
                    <label className="form-field">
                      Dodaj faktycznego uczestnika
                      <select
                        value={addId}
                        onChange={(e) => setAddId(e.target.value)}
                      >
                        <option value="">Wybierz istniejący profil</option>
                        {people.data
                          ?.filter((p) => !chosen.has(p.id))
                          .map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.first_name} {p.last_name}
                              {p.nickname ? ` — ${p.nickname}` : ""}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label className="form-field">
                      Do drużyny
                      <select
                        value={addTo}
                        onChange={(e) => setAddTo(e.target.value as "A" | "B")}
                      >
                        <option value="A">A</option>
                        <option value="B">B</option>
                      </select>
                    </label>
                    <button
                      className="button"
                      disabled={
                        !addId ||
                        chosen.size >= 14 ||
                        (addTo === "A" ? current.a : current.b).length >= 7
                      }
                      onClick={add}
                    >
                      Dodaj do składu
                    </button>
                  </div>
                )}
                {!validRoster && (
                  <p className="form-error" role="alert">
                    Popraw liczebność: od 2 do 14 obecnych, po 1–7 na stronę,
                    różnica najwyżej 1.
                  </p>
                )}
                {Object.values(changes).map((change) => {
                  const person = people.data?.find(
                    (p) => p.id === change.player_id,
                  );
                  return (
                    <div
                      className="historical-presence-change"
                      key={change.player_id}
                    >
                      <strong>
                        {person?.first_name} {person?.last_name}
                      </strong>
                      <label className="form-field">
                        Poprawna obecność
                        <select
                          value={change.value}
                          disabled={change.value === "present"}
                          onChange={(e) => {
                            setChanges({
                              ...changes,
                              [change.player_id]: {
                                ...change,
                                value: e.target
                                  .value as PresenceChange["value"],
                              },
                            });
                            setPreview(null);
                          }}
                        >
                          {change.value === "present" ? (
                            <option value="present">Obecny/a</option>
                          ) : (
                            <>
                              <option value="no_show">
                                Nieobecność bez odwołania
                              </option>
                              <option value="excused">
                                Usprawiedliwiona nieobecność
                              </option>
                            </>
                          )}
                        </select>
                      </label>
                      <label className="form-field">
                        Prywatny powód korekty obecności
                        <textarea
                          aria-label="Prywatny powód korekty obecności"
                          maxLength={500}
                          required
                          value={change.reason}
                          onChange={(e) => {
                            setChanges({
                              ...changes,
                              [change.player_id]: {
                                ...change,
                                reason: e.target.value,
                              },
                            });
                            setPreview(null);
                          }}
                        />
                        <small>Tylko dla organizatora i tego zawodnika.</small>
                      </label>
                    </div>
                  );
                })}
              </details>
            </>
          )}
          <div className="room-actions">
            {saved && (
              <button className="button" onClick={() => setEditing(false)}>
                Anuluj korektę
              </button>
            )}
            <button
              className="button"
              disabled={!canPreview || locked}
              onClick={showPreview}
            >
              Pokaż podgląd punktów
            </button>
          </div>
          {preview && (
            <div
              className="confirmation-panel result-preview"
              role="region"
              aria-label="Podgląd wyniku i punktów"
            >
              <h3>
                {preview.sets_a}:{preview.sets_b} w setach
              </h3>
              {preview.sets_a + preview.sets_b === 0 ? (
                <p>
                  Spotkanie zostanie zamknięte bez rozegranych setów. Bez wpisów
                  ELO za ten mecz.
                </p>
              ) : (
                <>
                  <div className="result-deltas">
                    <span>
                      A <strong>{delta(preview.outcome.delta_a)}</strong>
                    </span>
                    <span>
                      B <strong>{delta(preview.outcome.delta_b)}</strong>
                    </span>
                  </div>
                  <p className="form-note">
                    Na osobę w drużynie. Średnie przed meczem:{" "}
                    {points(preview.outcome.mean_a)} /{" "}
                    {points(preview.outcome.mean_b)}. Oczekiwany udział setów A:{" "}
                    {points(Number(preview.outcome.expected_a) * 100)}%.
                  </p>
                </>
              )}
              <p className="form-note">
                Przeliczone spotkania od tego meczu:{" "}
                {preview.recalculated_meetings}. Publikacja wyniku i rankingu
                nastąpi razem.
              </p>
              <button
                className="button primary"
                disabled={locked || !canPreview}
                onClick={commit}
              >
                {saved ? "Zatwierdź korektę" : "Zapisz wynik i ranking"}
              </button>
            </div>
          )}
        </fieldset>
      )}
      {action.error && (
        <p className="form-error" role="alert">
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
    </div>
  );
}
