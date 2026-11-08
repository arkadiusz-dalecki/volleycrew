import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, message, unwrap } from "../../lib/api/client";

export function OfferManager({
  meetingId,
  termVersion,
}: {
  meetingId: string;
  termVersion: number;
}) {
  const client = useQueryClient();
  const offers = useQuery({
    queryKey: ["seat-offers", meetingId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/admin/meetings/{meeting_id}/offers", {
          params: { path: { meeting_id: meetingId } },
        }),
      ),
    refetchInterval: 30_000,
  });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [closing, setClosing] = useState<string | null>(null);
  async function act(id: string, playerId: string, close: boolean) {
    setBusy(true);
    setNotice("");
    try {
      if (close)
        unwrap(
          await api.POST("/api/v1/admin/offers/{offer_id}/close", {
            params: { path: { offer_id: id } },
            body: { term_version: termVersion, reason: "no-response" },
          }),
        );
      else
        unwrap(
          await api.POST("/api/v1/admin/meetings/{meeting_id}/offers", {
            params: { path: { meeting_id: meetingId } },
            body: { term_version: termVersion, player_id: playerId },
          }),
        );
      setClosing(null);
      setNotice(
        close
          ? "Zgłoszenie wycofane. Miejsce przechodzi do kolejnej osoby z rezerwy, jeśli taka jest."
          : "Propozycja jest aktywna. Powiadom tę osobę na Messengerze.",
      );
    } catch (e) {
      setNotice(message(e));
    } finally {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["seat-offers"] }),
        client.invalidateQueries({ queryKey: ["meeting"] }),
        client.invalidateQueries({ queryKey: ["next-meeting"] }),
        client.invalidateQueries({ queryKey: ["participation"] }),
        client.invalidateQueries({ queryKey: ["calendar"] }),
      ]);
      setBusy(false);
    }
  }
  return (
    <section className="card offer-manager">
      <h2>Miejsca z rezerwy</h2>
      <p className="form-note">
        Kontaktujesz się ręcznie na Messengerze. Rezerwacja czeka na odpowiedź
        bez automatycznego limitu czasu.
      </p>
      {offers.isPending ? (
        <p role="status">Wczytujemy propozycje…</p>
      ) : offers.isError ? (
        <div role="alert">
          <p>Nie udało się pobrać rezerwacji.</p>
          <button className="button" onClick={() => void offers.refetch()}>
            Ponów
          </button>
        </div>
      ) : !offers.data.length ? (
        <p className="form-note">
          Nie ma miejsc oczekujących na potwierdzenie z rezerwy.
        </p>
      ) : (
        <ul className="offer-list">
          {offers.data.map((offer) => (
            <li key={offer.id}>
              <strong>
                {offer.player.first_name} {offer.player.last_name}
                {offer.player.nickname ? ` — ${offer.player.nickname}` : ""}
              </strong>
              <small>
                {offer.state === "reserved"
                  ? "Miejsce zarezerwowane · propozycja jeszcze niewysłana"
                  : "Propozycja aktywna · czekamy na potwierdzenie"}
              </small>
              <div className="participation-actions">
                {offer.state === "reserved" && (
                  <button
                    className="button primary small"
                    disabled={busy}
                    onClick={() => void act(offer.id, offer.player.id, false)}
                  >
                    Zaproponuj miejsce
                  </button>
                )}
                <button
                  className="button small"
                  disabled={busy}
                  onClickCapture={(event) => event.currentTarget.focus()}
                  onClick={() => setClosing(offer.id)}
                >
                  Przekaż dalej
                </button>
              </div>
              {closing === offer.id && (
                <ConfirmDialog
                  title="Przekazać miejsce kolejnej osobie?"
                  busy={busy}
                  onDismiss={() => setClosing(null)}
                >
                  {notice && (
                    <p role="alert" className="form-error">
                      {notice}
                    </p>
                  )}
                  <p>
                    Wycofasz zgłoszenie tej osoby z powodu braku odpowiedzi. Nie
                    otrzyma oznaczenia nieobecności. Miejsce zostanie
                    zarezerwowane dla następnej osoby w kolejce.
                  </p>
                  <div className="participation-actions">
                    <button
                      className="button small"
                      disabled={busy}
                      onClickCapture={(event) => event.currentTarget.focus()}
                      onClick={() => setClosing(null)}
                    >
                      Anuluj
                    </button>
                    <button
                      className="button primary small"
                      disabled={busy}
                      onClick={() => void act(offer.id, offer.player.id, true)}
                    >
                      Potwierdź przekazanie
                    </button>
                  </div>
                </ConfirmDialog>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="form-notice" role="status">
        {notice}
      </p>
    </section>
  );
}
