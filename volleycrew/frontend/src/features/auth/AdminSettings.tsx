import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Link } from "react-router-dom";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, ShieldCheck } from "lucide-react";
import { api, message, unwrap } from "../../lib/api/client";
import { priorityLabel } from "./labels";

export function AdminSettings() {
  const players = useQuery({
    queryKey: ["admin-players"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/players")),
  });
  const invites = useQuery({
    queryKey: ["admin-invites"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/invites")),
  });
  const [link, setLink] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState<{
    id: string;
    active: boolean;
    name: string;
  } | null>(null);
  const client = useQueryClient();
  async function action(run: () => Promise<void>) {
    setNotice("");
    setBusy(true);
    try {
      await run();
    } catch (e) {
      setNotice(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function createInvite() {
    await action(async () => {
      const data = unwrap(await api.POST("/api/v1/admin/invites"));
      setLink(data.url);
      await client.invalidateQueries({ queryKey: ["admin-invites"] });
    });
  }
  async function revoke(id: string) {
    await action(async () => {
      unwrap(
        await api.POST("/api/v1/admin/invites/{invite_id}/revoke", {
          params: { path: { invite_id: id } },
        }),
      );
      setLink("");
      await client.invalidateQueries({ queryKey: ["admin-invites"] });
    });
  }
  async function reset(id: string) {
    await action(async () => {
      const data = unwrap(
        await api.POST("/api/v1/admin/players/{player_id}/pin-reset", {
          params: { path: { player_id: id } },
        }),
      );
      setLink(data.url);
      setNotice(
        "Przekaż ten jednorazowy link zawodnikowi. Działa przez 30 minut.",
      );
    });
  }
  async function changePriority(
    id: string,
    priority: "founder" | "player" | "guest",
  ) {
    await action(async () => {
      unwrap(
        await api.PATCH("/api/v1/admin/players/{player_id}", {
          params: { path: { player_id: id } },
          body: { priority_status: priority },
        }),
      );
      await Promise.all([
        client.invalidateQueries({ queryKey: ["admin-players"] }),
        client.invalidateQueries({ queryKey: ["meeting"] }),
        client.invalidateQueries({ queryKey: ["participation"] }),
        client.invalidateQueries({ queryKey: ["seat-offers"] }),
        client.invalidateQueries({ queryKey: ["next-meeting"] }),
        client.invalidateQueries({ queryKey: ["calendar"] }),
        client.invalidateQueries({ queryKey: ["me"] }),
      ]);
    });
  }
  async function block() {
    if (!confirmation) return;
    const value = confirmation;
    await action(async () => {
      unwrap(
        await api.PATCH("/api/v1/admin/players/{player_id}", {
          params: { path: { player_id: value.id } },
          body: { is_active: !value.active },
        }),
      );
      setConfirmation(null);
      await client.invalidateQueries({ queryKey: ["admin-players"] });
    });
  }
  return (
    <>
      <div className="page-heading">
        <h1>Ustawienia ekipy</h1>
        <p>Zaproszenia i dostęp zawodników. Tylko dla organizatora.</p>
      </div>
      <div className="admin-settings">
        <section className="card">
          <div className="section-title">
            <h2>Link do ekipy</h2>
            <ShieldCheck size={20} />
          </div>
          <p className="form-note">
            Jedno zaproszenie możesz udostępnić wielu osobom. Działa, dopóki go
            nie unieważnisz.
          </p>
          <button
            className="button primary"
            onClick={() => void createInvite()}
            disabled={busy}
          >
            Utwórz link z zaproszeniem
          </button>
          {link && (
            <div className="share-link">
              <label className="form-field">
                Link do przekazania
                <input
                  readOnly
                  value={link}
                  onFocus={(e) => e.target.select()}
                />
              </label>
              <button
                className="button"
                onClick={() =>
                  void navigator.clipboard
                    .writeText(link)
                    .then(() => setNotice("Link skopiowany."))
                    .catch(() =>
                      setNotice("Zaznacz i skopiuj link z pola powyżej."),
                    )
                }
              >
                <Copy size={16} /> Kopiuj
              </button>
              <p className="form-note">
                Pełny link pokazujemy tylko po utworzeniu. Zapisz go, jeśli
                chcesz udostępnić go później.
              </p>
            </div>
          )}
          <p className="form-notice" role="status">
            {notice}
          </p>
          {invites.isPending ? (
            <p role="status">Wczytujemy zaproszenia…</p>
          ) : invites.isError ? (
            <div role="alert">
              <p>Nie udało się pobrać zaproszeń.</p>
              <button className="button" onClick={() => void invites.refetch()}>
                Ponów
              </button>
            </div>
          ) : (
            <ul className="invite-list">
              {invites.data.map((invite) => (
                <li key={invite.id} data-testid={`invite-${invite.id}`}>
                  <span>
                    {new Date(invite.created_at).toLocaleDateString("pl-PL")} ·{" "}
                    {invite.revoked_at ? "Unieważnione" : "Aktywne"}
                  </span>
                  {!invite.revoked_at && (
                    <button
                      className="button small"
                      disabled={busy}
                      onClick={() => void revoke(invite.id)}
                    >
                      Unieważnij
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card">
          <h2>Zawodnicy</h2>
          {players.isPending ? (
            <p role="status">Wczytujemy zawodników…</p>
          ) : players.isError ? (
            <div role="alert">
              <p>Nie udało się pobrać zawodników.</p>
              <button className="button" onClick={() => void players.refetch()}>
                Ponów
              </button>
            </div>
          ) : (
            <ul className="admin-player-list">
              {players.data.map((player) => (
                <li key={player.id}>
                  <div>
                    <strong>
                      {player.first_name} {player.last_name}
                      {player.nickname ? ` — ${player.nickname}` : ""}
                    </strong>
                    <small>
                      {priorityLabel(player.priority_status)} ·{" "}
                      {player.is_active
                        ? "Aktywny profil"
                        : "Profil zablokowany"}
                      {player.role === "admin" ? " · Administrator" : ""}
                    </small>
                  </div>
                  <div className="row-actions">
                    <Link
                      className="button small"
                      to={`/admin/players/${player.id}/history`}
                    >
                      Historia obecności
                    </Link>
                    <label className="priority-select">
                      Status (prywatny)
                      <select
                        aria-label={`Status: ${player.first_name} ${player.last_name}`}
                        value={player.priority_status}
                        disabled={busy}
                        onChange={(e) =>
                          void changePriority(
                            player.id,
                            e.target.value as "founder" | "player" | "guest",
                          )
                        }
                      >
                        <option value="founder">Założyciel</option>
                        <option value="player">Zawodnik</option>
                        <option value="guest">Gość</option>
                      </select>
                    </label>
                    {player.is_active && (
                      <button
                        className="button small"
                        disabled={busy}
                        onClick={() => void reset(player.id)}
                      >
                        Reset PIN-u
                      </button>
                    )}
                    {player.role !== "admin" && (
                      <button
                        className="button small"
                        disabled={busy}
                        onClickCapture={(event) => event.currentTarget.focus()}
                        onClick={() =>
                          setConfirmation({
                            id: player.id,
                            active: player.is_active,
                            name: `${player.first_name} ${player.last_name}`,
                          })
                        }
                      >
                        {player.is_active ? "Zablokuj" : "Odblokuj"}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      {confirmation && (
        <ConfirmDialog
          title={
            confirmation.active ? "Zablokować profil?" : "Odblokować profil?"
          }
          busy={busy}
          onDismiss={() => setConfirmation(null)}
        >
          {notice && (
            <p className="form-error" role="alert">
              {notice}
            </p>
          )}
          <p>{confirmation.name}</p>
          <p className="form-note">
            {confirmation.active
              ? "Zawodnik zostanie wylogowany i utraci dostęp. Jego przyszłe miejsca, rezerwacje i oferty zostaną zwolnione. Historia i wyniki pozostają zachowane."
              : "Zawodnik będzie mógł ponownie zalogować się swoim PIN-em."}
          </p>
          <div className="row-actions">
            <button
              className="button"
              disabled={busy}
              onClick={() => setConfirmation(null)}
            >
              Anuluj
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => void block()}
            >
              Potwierdź
            </button>
          </div>
        </ConfirmDialog>
      )}
    </>
  );
}
