import { ResultEditor } from "../results/ResultEditor";
import { SignatureListButton } from "../documents/SignatureList";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, ShieldCheck, Shuffle, Scale } from "lucide-react";
import { Link } from "react-router-dom";
import { api, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { Court, type Teams, type TeamPlayer } from "./Court";
import { useRoomAction } from "./useRoomAction";
type Attendance = components["schemas"]["AttendanceView"];
type State = "present" | "absent" | "unknown";
const headers = (key: string) => ({ "Idempotency-Key": key });

export function RoomPanel({ meetingId }: { meetingId: string }) {
  const attendance = useQuery({
    queryKey: ["attendance", meetingId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/admin/meetings/{meeting_id}/attendance", {
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
    refetchInterval: 30_000,
  });
  if (attendance.isPending || teams.isPending)
    return (
      <section className="card" role="status">
        Wczytujemy panel organizatora…
      </section>
    );
  if (
    (attendance.isError && attendance.data === undefined) ||
    (teams.isError && teams.data === undefined)
  )
    return (
      <section className="card">
        <p role="alert">Nie udało się wczytać panelu organizatora.</p>
        <button
          className="button"
          onClick={() => {
            void attendance.refetch();
            void teams.refetch();
          }}
        >
          Ponów
        </button>
      </section>
    );
  if (attendance.data!.status === "cancelled") return null;
  return (
    <>
      {(attendance.isError || teams.isError) && (
        <p role="status" className="connection-notice">
          Nie udało się odświeżyć panelu. Pokazujemy ostatnio pobrane dane;
          niezapisane zmiany pozostają w formularzu.
        </p>
      )}
      <RoomEditor attendance={attendance.data!} teams={teams.data ?? null} />
    </>
  );
}

function RoomEditor({
  attendance,
  teams,
}: {
  attendance: Attendance;
  teams: Teams | null;
}) {
  const action = useRoomAction();
  const params = { path: { meeting_id: attendance.meeting_id } };
  const [tab, setTab] = useState<"attendance" | "teams" | "result">(
    attendance.status === "completed"
      ? "result"
      : attendance.confirmed_at
        ? "teams"
        : "attendance",
  );
  const [checks, setChecks] = useState<{
    version: number;
    values: Record<string, State>;
  } | null>(null);
  const [teamEdit, setTeamEdit] = useState<{
    version: number;
    a: TeamPlayer[];
    b: TeamPlayer[];
  } | null>(null);
  const [selected, setSelected] = useState("");
  const [confirmation, setConfirmation] = useState(false);
  const [reason, setReason] = useState("");
  const [admitId, setAdmitId] = useState("");
  const [releaseId, setReleaseId] = useState("");
  const [correction, setCorrection] = useState<{
    event: string;
    value: "present" | "no_show" | "excused";
    name: string;
  } | null>(null);
  const [correctionReason, setCorrectionReason] = useState("");
  const people = useQuery({
    queryKey: ["admin-players"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/players")),
  });
  const locked = action.busy || action.canRetry;
  const presenceLocked = ["teams_confirmed", "completed"].includes(
    attendance.status,
  );
  const staleChecks = checks !== null && checks.version !== attendance.version;
  const staleTeams =
    teamEdit !== null && teamEdit.version !== attendance.version;
  const values =
    checks?.values ??
    Object.fromEntries(
      attendance.players.map((p) => [p.player.id, p.draft_state]),
    );
  const currentTeams =
    teams && teamEdit
      ? {
          ...teams,
          team_a: teamEdit.a,
          team_b: teamEdit.b,
          average_a:
            teamEdit.a.reduce((sum, p) => sum + p.rating, 0) /
            teamEdit.a.length,
          average_b:
            teamEdit.b.reduce((sum, p) => sum + p.rating, 0) /
            teamEdit.b.length,
        }
      : teams;
  function updateChecks(id: string, value: State) {
    setChecks({
      version: checks?.version ?? attendance.version,
      values: { ...values, [id]: value },
    });
    setConfirmation(false);
  }
  function selectPlayer(id: string) {
    if (!currentTeams || !teams) return;
    const a = [...currentTeams.team_a],
      b = [...currentTeams.team_b];
    const previousA = a.findIndex((p) => p.player.id === selected),
      previousB = b.findIndex((p) => p.player.id === selected);
    const nextA = a.findIndex((p) => p.player.id === id),
      nextB = b.findIndex((p) => p.player.id === id);
    if (previousA >= 0 && nextB >= 0)
      [a[previousA], b[nextB]] = [b[nextB], a[previousA]];
    else if (previousB >= 0 && nextA >= 0)
      [a[nextA], b[previousB]] = [b[previousB], a[nextA]];
    else {
      setSelected(id === selected ? "" : id);
      return;
    }
    setTeamEdit({ version: teamEdit?.version ?? attendance.version, a, b });
    setSelected("");
  }
  function transfer() {
    if (!currentTeams) return;
    const a = [...currentTeams.team_a],
      b = [...currentTeams.team_b];
    const fromA = a.findIndex((p) => p.player.id === selected),
      fromB = b.findIndex((p) => p.player.id === selected);
    if (fromA >= 0 && a.length > b.length) b.push(...a.splice(fromA, 1));
    else if (fromB >= 0 && b.length > a.length) a.push(...b.splice(fromB, 1));
    else return;
    setTeamEdit({ version: teamEdit?.version ?? attendance.version, a, b });
    setSelected("");
  }
  function generate(mode: "random" | "balanced" | "preliminary") {
    void action.run(
      async (key) =>
        unwrap(
          await api.POST("/api/v1/admin/meetings/{meeting_id}/teams/generate", {
            params: { ...params, header: headers(key) },
            body: { expected_version: attendance.version, mode },
          }),
        ),
      () => {
        setTeamEdit(null);
        setSelected("");
      },
    );
  }
  const selectedInLarger =
    !!currentTeams &&
    !!selected &&
    ((currentTeams.team_a.length > currentTeams.team_b.length &&
      currentTeams.team_a.some((p) => p.player.id === selected)) ||
      (currentTeams.team_b.length > currentTeams.team_a.length &&
        currentTeams.team_b.some((p) => p.player.id === selected)));
  const eligible =
    people.data?.filter(
      (p) =>
        p.is_active &&
        !attendance.players.some((row) => row.player.id === p.id) &&
        !attendance.reservations.some((row) => row.player.id === p.id),
    ) ?? [];
  return (
    <section className="card room-panel" aria-label="Panel organizatora">
      <div className="section-title">
        <h2>
          <ShieldCheck size={20} /> Panel organizatora
        </h2>
        <SignatureListButton
          meetingId={attendance.meeting_id}
          ready={!!attendance.confirmed_at}
        />
      </div>
      <div className="room-steps" aria-label="Etapy obsługi spotkania">
        <button
          aria-pressed={tab === "attendance"}
          onClick={() => setTab("attendance")}
        >
          01 Obecność {attendance.confirmed_at && <Check size={14} />}
        </button>
        <button
          aria-pressed={tab === "teams"}
          disabled={!attendance.confirmed_at}
          onClick={() => setTab("teams")}
        >
          02 Drużyny {teams?.state === "confirmed" && <Check size={14} />}
        </button>
        <button
          aria-pressed={tab === "result"}
          disabled={
            !["teams_confirmed", "completed"].includes(attendance.status)
          }
          onClick={() => setTab("result")}
        >
          03 Wynik {attendance.status === "completed" && <Check size={14} />}
        </button>
      </div>
      {action.error && (
        <p className="form-error" role="alert">
          {action.error}
        </p>
      )}
      {action.canRetry && (
        <div className="confirmation-panel">
          <p>
            Nie mamy potwierdzenia zapisu. Ponowienie sprawdzi tę samą operację.
          </p>
          <button
            className="button primary"
            disabled={action.busy}
            onClick={() => void action.retry()}
          >
            Ponów tę operację
          </button>
        </div>
      )}
      {tab === "result" ? (
        <ResultEditor
          meetingId={attendance.meeting_id}
          version={attendance.version}
        />
      ) : tab === "attendance" ? (
        <>
          <p className="form-note">
            {attendance.confirmed_at
              ? "Obecność zatwierdzona. Każda poprawka wymaga powodu; wpis źródłowy pozostaje w prywatnej historii."
              : "Sprawdź, kto jest już na sali. Szkic nie tworzy oznaczeń nieobecności w historii."}
          </p>
          {presenceLocked && (
            <p className="form-note">
              {attendance.status === "completed"
                ? "Obecność i skład zakończonego spotkania poprawisz razem z wynikiem w kroku 03."
                : "Aby zmienić faktyczną obecność, najpierw otwórz drużyny do poprawy."}
            </p>
          )}
          {staleChecks && (
            <p className="form-error" role="alert">
              Lista zmieniła się od rozpoczęcia edycji. Zachowaliśmy Twój szkic.{" "}
              <button
                className="button small"
                onClick={() => {
                  setChecks(null);
                  setConfirmation(false);
                }}
              >
                Wczytaj aktualną listę
              </button>
            </p>
          )}
          {!attendance.confirmed_at && (
            <button
              className="button small"
              disabled={locked || staleChecks}
              onClick={() => {
                setChecks({
                  version: checks?.version ?? attendance.version,
                  values: Object.fromEntries(
                    attendance.players.map((p) => [
                      p.player.id,
                      "present" as State,
                    ]),
                  ),
                });
                setConfirmation(false);
              }}
            >
              Wszyscy obecni
            </button>
          )}
          <ul className="attendance-list">
            {attendance.players.map((row) => (
              <li key={row.player.id}>
                <div className="attendance-name">
                  <strong>
                    {row.player.first_name} {row.player.last_name}
                  </strong>
                  {row.player.nickname && <small>{row.player.nickname}</small>}
                  {attendance.confirmed_at && (
                    <Link
                      className="text-link"
                      to={`/admin/players/${row.player.id}/history`}
                    >
                      Prywatna historia
                    </Link>
                  )}
                </div>
                {attendance.confirmed_at ? (
                  <div className="attendance-controls">
                    <span className={`presence-label ${row.confirmed_state}`}>
                      {row.confirmed_state === "present"
                        ? "Obecny/a"
                        : "Nieobecny/a"}
                    </span>
                    {row.event_id && (
                      <button
                        className="button small"
                        disabled={locked}
                        onClick={() => {
                          setCorrection({
                            event: row.event_id!,
                            value:
                              row.confirmed_state === "present"
                                ? "no_show"
                                : "present",
                            name: `${row.player.first_name} ${row.player.last_name}`,
                          });
                          setCorrectionReason("");
                        }}
                      >
                        Korekta
                      </button>
                    )}
                  </div>
                ) : (
                  <div
                    className="attendance-controls"
                    role="group"
                    aria-label={`Obecność: ${row.player.first_name} ${row.player.last_name}`}
                  >
                    <button
                      className="button small"
                      aria-pressed={values[row.player.id] === "present"}
                      disabled={locked || staleChecks}
                      onClick={() => updateChecks(row.player.id, "present")}
                    >
                      Obecny/a
                    </button>
                    <button
                      className="button small"
                      aria-pressed={values[row.player.id] === "absent"}
                      disabled={locked || staleChecks}
                      onClick={() => updateChecks(row.player.id, "absent")}
                    >
                      Nieobecny/a
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
          {!attendance.players.length && (
            <p className="form-note">
              Nie ma potwierdzonych uczestników. Oczekująca rezerwacja wymaga
              osobnej decyzji.
            </p>
          )}
          {!attendance.confirmed_at && (
            <div className="room-actions">
              <button
                className="button"
                disabled={locked || !checks || staleChecks}
                onClick={() =>
                  void action.run(
                    async (key) =>
                      unwrap(
                        await api.PUT(
                          "/api/v1/admin/meetings/{meeting_id}/attendance",
                          {
                            params: { ...params, header: headers(key) },
                            body: {
                              expected_version: checks!.version,
                              players: Object.entries(checks!.values).map(
                                ([player_id, state]) => ({ player_id, state }),
                              ),
                            },
                          },
                        ),
                      ),
                    () => setChecks(null),
                  )
                }
              >
                Zapisz szkic obecności
              </button>
              <button
                className="button primary"
                disabled={
                  locked ||
                  !!checks ||
                  !attendance.can_confirm ||
                  attendance.players.some((p) => p.draft_state === "unknown")
                }
                onClick={() => setConfirmation(true)}
              >
                Zatwierdź obecność
              </button>
            </div>
          )}
          {!attendance.confirmed_at &&
            attendance.can_confirm &&
            !staleChecks &&
            (checks ? (
              <p className="form-note" role="status">
                Masz niezapisane zmiany. Oznacz obecność wszystkich osób i
                kliknij „Zapisz szkic obecności”, aby odblokować zatwierdzenie.
              </p>
            ) : attendance.players.some((p) => p.draft_state === "unknown") ? (
              <p className="form-note" role="status">
                Oznacz każdą osobę jako obecną lub nieobecną albo wybierz
                „Wszyscy obecni”. Następnie kliknij „Zapisz szkic obecności” —
                wtedy zatwierdzenie będzie dostępne.
              </p>
            ) : null)}
          {!attendance.confirmed_at && !attendance.can_confirm && (
            <p className="form-note">
              Zatwierdzenie jest dostępne od godziny rozpoczęcia spotkania.
              Szkic możesz przygotować wcześniej.
            </p>
          )}
          {confirmation && (
            <div
              className="confirmation-panel"
              role="region"
              aria-label="Potwierdzenie obecności"
            >
              <h3>Zapisać faktyczną obecność?</h3>
              <p>
                Nieobecni z potwierdzonym miejscem otrzymają prywatny wpis
                „nieobecność bez odwołania”. Ich miejsca przejdą do obsługi
                rezerwy.
              </p>
              <div className="room-actions">
                <button
                  className="button"
                  disabled={locked}
                  onClick={() => setConfirmation(false)}
                >
                  Wróć do listy
                </button>
                <button
                  className="button primary"
                  disabled={locked || !!checks || !attendance.can_confirm}
                  onClick={() =>
                    void action.run(
                      async (key) =>
                        unwrap(
                          await api.POST(
                            "/api/v1/admin/meetings/{meeting_id}/attendance/confirm",
                            {
                              params: { ...params, header: headers(key) },
                              body: { expected_version: attendance.version },
                            },
                          ),
                        ),
                      () => {
                        setConfirmation(false);
                        setTab("teams");
                      },
                    )
                  }
                >
                  Potwierdź sprawdzoną obecność
                </button>
              </div>
            </div>
          )}
          {correction && (
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
                          params: { ...params, header: headers(key) },
                          body: {
                            expected_version: attendance.version,
                            event_id: correction.event,
                            value: correction.value,
                            reason: correctionReason,
                          },
                        },
                      ),
                    ),
                  () => setCorrection(null),
                );
              }}
            >
              <h3>Korekta: {correction.name}</h3>
              <label className="form-field">
                Poprawny stan
                <select
                  value={correction.value}
                  onChange={(e) =>
                    setCorrection({
                      ...correction,
                      value: e.target.value as typeof correction.value,
                    })
                  }
                >
                  <option value="present" disabled={presenceLocked}>
                    Obecny/a (także spóźniony/a)
                  </option>
                  <option value="no_show" disabled={presenceLocked}>
                    Nieobecność bez odwołania
                  </option>
                  <option
                    value="excused"
                    disabled={
                      presenceLocked &&
                      attendance.players.find(
                        (p) => p.event_id === correction.event,
                      )?.confirmed_state === "present"
                    }
                  >
                    Usprawiedliwiona nieobecność
                  </option>
                </select>
              </label>
              <label className="form-field">
                Powód korekty
                <textarea
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  required
                  maxLength={500}
                />
              </label>
              <div className="room-actions">
                <button
                  type="button"
                  className="button"
                  disabled={locked}
                  onClick={() => setCorrection(null)}
                >
                  Anuluj korektę
                </button>
                <button
                  className="button primary"
                  disabled={locked || !correctionReason.trim()}
                >
                  Zapisz korektę
                </button>
              </div>
            </form>
          )}
          {!presenceLocked && (
            <details className="room-admission">
              <summary>Osoby z rezerwy i dopisanie na sali</summary>
              <p className="form-note">
                Potwierdzaj wyłącznie osoby fizycznie obecne. Rezerwacja chroni
                miejsce swojego adresata. Komunikację prowadzisz na Messengerze.
              </p>
              {attendance.reservations.map((row) => (
                <div className="room-reservation" key={row.player.id}>
                  <strong>
                    {row.player.first_name} {row.player.last_name}
                  </strong>
                  <div className="room-actions">
                    <button
                      className="button small"
                      disabled={locked}
                      onClick={() =>
                        void action.run(async (key) =>
                          unwrap(
                            await api.POST(
                              "/api/v1/admin/meetings/{meeting_id}/attendance/admit",
                              {
                                params: { ...params, header: headers(key) },
                                body: {
                                  expected_version: attendance.version,
                                  player_id: row.player.id,
                                },
                              },
                            ),
                          ),
                        )
                      }
                    >
                      Jest na sali — potwierdź
                    </button>
                    <button
                      className="button small"
                      disabled={locked}
                      onClick={() => setReleaseId(row.player.id)}
                    >
                      Zwolnij rezerwację
                    </button>
                  </div>
                  {releaseId === row.player.id && (
                    <div className="confirmation-panel">
                      <p>
                        Wycofać tę rezerwację i przekazać miejsce kolejnej
                        osobie? Bez oznaczenia nieobecności.
                      </p>
                      <div className="room-actions">
                        <button
                          className="button small"
                          onClick={() => setReleaseId("")}
                        >
                          Zachowaj
                        </button>
                        <button
                          className="button small"
                          disabled={locked}
                          onClick={() =>
                            void action.run(
                              async (key) =>
                                unwrap(
                                  await api.POST(
                                    "/api/v1/admin/meetings/{meeting_id}/attendance/release-reservation",
                                    {
                                      params: {
                                        ...params,
                                        header: headers(key),
                                      },
                                      body: {
                                        expected_version: attendance.version,
                                        player_id: row.player.id,
                                      },
                                    },
                                  ),
                                ),
                              () => setReleaseId(""),
                            )
                          }
                        >
                          Zwolnij i przekaż dalej
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <p className="form-note">
                Wolne, niezarezerwowane miejsca: {attendance.free_count}.
              </p>
              {people.isError ? (
                <button
                  className="button"
                  onClick={() => void people.refetch()}
                >
                  Ponów wczytanie profili
                </button>
              ) : (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void action.run(
                      async (key) =>
                        unwrap(
                          await api.POST(
                            "/api/v1/admin/meetings/{meeting_id}/attendance/admit",
                            {
                              params: { ...params, header: headers(key) },
                              body: {
                                expected_version: attendance.version,
                                player_id: admitId,
                              },
                            },
                          ),
                        ),
                      () => setAdmitId(""),
                    );
                  }}
                >
                  <label className="form-field">
                    Dopisz istniejący profil
                    <select
                      required
                      value={admitId}
                      onChange={(e) => setAdmitId(e.target.value)}
                    >
                      <option value="">Wybierz osobę obecną na sali</option>
                      {eligible.map((p) => (
                        <option value={p.id} key={p.id}>
                          {p.first_name} {p.last_name}
                          {p.nickname ? ` — ${p.nickname}` : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="button"
                    disabled={locked || !admitId || !attendance.free_count}
                  >
                    Potwierdź i dopisz obecną osobę
                  </button>
                </form>
              )}
            </details>
          )}
        </>
      ) : (
        <>
          {teams?.state !== "confirmed" && (
            <>
              <p className="form-note">
                Podział obejmuje wyłącznie faktycznie obecnych. Wybierz sposób
                podziału.
              </p>
              <div className="room-actions">
                <button
                  className="button primary"
                  disabled={locked || !!teamEdit}
                  onClick={() => generate("preliminary")}
                >
                  Użyj wstępnego podziału
                </button>
                <button
                  className="button"
                  disabled={locked || !!teamEdit}
                  onClick={() => generate("random")}
                >
                  <Shuffle size={17} /> Losuj składy
                </button>
                <button
                  className="button"
                  disabled={locked || !!teamEdit}
                  onClick={() => generate("balanced")}
                >
                  <Scale size={17} /> Wyrównaj według rankingu
                </button>
              </div>
            </>
          )}
          {staleTeams && (
            <p className="form-error" role="alert">
              Skład lub obecność zmieniły się w innej karcie. Twoje poprawki są
              zachowane.{" "}
              <button
                className="button small"
                onClick={() => {
                  setTeamEdit(null);
                  setSelected("");
                }}
              >
                Wczytaj aktualne składy
              </button>
            </p>
          )}
          {currentTeams ? (
            <>
              <p className="room-team-state">
                {teams?.state === "confirmed"
                  ? "Składy zatwierdzone — widoczne dla ekipy"
                  : "Szkic — widoczny tylko dla organizatora"}
              </p>
              {teams?.state === "draft" && (
                <p className="form-note" role="status">
                  {selected
                    ? "Teraz dotknij osoby z przeciwnej drużyny, aby je zamienić."
                    : "Dotknij zawodnika, a potem osoby z drugiej drużyny. Zamiana działa także przy 7:7."}
                </p>
              )}
              <Court
                teams={currentTeams}
                selected={selected}
                disabled={locked || staleTeams}
                onSelect={teams?.state === "draft" ? selectPlayer : undefined}
              />
              {selectedInLarger && (
                <button
                  className="button"
                  disabled={locked || staleTeams}
                  onClick={transfer}
                >
                  Przenieś wybraną osobę do mniejszej drużyny
                </button>
              )}
              {teams?.state === "draft" ? (
                <div className="room-actions">
                  <button
                    className="button"
                    disabled={locked || !teamEdit || staleTeams}
                    onClick={() =>
                      void action.run(
                        async (key) =>
                          unwrap(
                            await api.PUT(
                              "/api/v1/admin/meetings/{meeting_id}/teams",
                              {
                                params: { ...params, header: headers(key) },
                                body: {
                                  expected_version: teamEdit!.version,
                                  team_a: teamEdit!.a.map((p) => p.player.id),
                                  team_b: teamEdit!.b.map((p) => p.player.id),
                                },
                              },
                            ),
                          ),
                        () => {
                          setTeamEdit(null);
                          setSelected("");
                        },
                      )
                    }
                  >
                    Zapisz poprawki składów
                  </button>
                  {teamEdit && (
                    <button
                      className="button"
                      disabled={locked}
                      onClick={() => {
                        setTeamEdit(null);
                        setSelected("");
                      }}
                    >
                      Odrzuć poprawki
                    </button>
                  )}
                  <button
                    className="button primary"
                    disabled={locked || !!teamEdit}
                    onClick={() =>
                      void action.run(async (key) =>
                        unwrap(
                          await api.POST(
                            "/api/v1/admin/meetings/{meeting_id}/teams/confirm",
                            {
                              params: { ...params, header: headers(key) },
                              body: { expected_version: attendance.version },
                            },
                          ),
                        ),
                      )
                    }
                  >
                    <Check size={17} /> Zatwierdź składy
                  </button>
                </div>
              ) : (
                attendance.status !== "completed" && (
                  <form
                    className="room-reopen"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void action.run(
                        async (key) =>
                          unwrap(
                            await api.POST(
                              "/api/v1/admin/meetings/{meeting_id}/teams/reopen",
                              {
                                params: { ...params, header: headers(key) },
                                body: {
                                  expected_version: attendance.version,
                                  reason,
                                },
                              },
                            ),
                          ),
                        () => setReason(""),
                      );
                    }}
                  >
                    <label className="form-field">
                      Powód otwarcia składów do poprawy
                      <textarea
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        required
                        maxLength={500}
                      />
                      <small>
                        Dotychczasowy skład pozostanie w historii zmian. Nowy
                        szkic wymaga ponownego zatwierdzenia.
                      </small>
                    </label>
                    <button
                      className="button"
                      disabled={locked || !reason.trim()}
                    >
                      Otwórz składy do poprawy
                    </button>
                  </form>
                )
              )}
            </>
          ) : (
            <p className="form-note">
              Nie ma jeszcze podziału. Potrzeba od 2 do 14 obecnych osób.
            </p>
          )}
        </>
      )}
    </section>
  );
}
