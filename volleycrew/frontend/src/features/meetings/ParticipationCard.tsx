import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Clock3, UserPlus, X } from "lucide-react";
import { api, message, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { dateLabel, hour } from "./dates";

type Meeting = components["schemas"]["MeetingDetail"];
export function ParticipationCard({ meeting }: { meeting: Meeting }) {
  const client = useQueryClient();
  const own = useQuery({
    queryKey: ["participation", meeting.id],
    enabled: meeting.persisted,
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/meetings/{meeting_id}/my-participation", {
          params: { path: { meeting_id: meeting.id } },
          signal,
        }),
      ),
    refetchInterval: 30_000,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const pending = useRef<{
    declaration: "going" | "not-going";
    key: string;
    term: number;
    late: boolean;
  } | null>(null);
  const state = own.data;
  async function refresh() {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["meeting"] }),
      client.invalidateQueries({ queryKey: ["next-meeting"] }),
      client.invalidateQueries({ queryKey: ["calendar"] }),
      client.invalidateQueries({ queryKey: ["participation"] }),
      client.invalidateQueries({ queryKey: ["seat-offers"] }),
    ]);
  }
  async function declare(declaration: "going" | "not-going") {
    setBusy(true);
    setError("");
    try {
      const persisted = meeting.persisted
        ? meeting
        : unwrap(
            await api.POST("/api/v1/meetings/resolve", {
              body: {
                schedule_version_id: meeting.schedule_version_id,
                source_date: meeting.source_date,
              },
            }),
          );
      const term = state?.term_version ?? persisted.term_version;
      const late =
        declaration === "not-going" && state?.cancellation_kind === "late";
      if (
        !pending.current ||
        pending.current.declaration !== declaration ||
        pending.current.term !== term ||
        pending.current.late !== late
      )
        pending.current = { declaration, term, late, key: crypto.randomUUID() };
      const result = await api.PUT(
        "/api/v1/meetings/{meeting_id}/my-declaration",
        {
          params: {
            path: { meeting_id: persisted.id },
            header: { "Idempotency-Key": pending.current.key },
          },
          body: { declaration, term_version: term, acknowledge_late: late },
        },
      );
      if (result.response.status >= 400 && result.response.status < 500)
        pending.current = null;
      const data = unwrap(result);
      pending.current = null;
      client.setQueryData(["participation", meeting.id], data.participation);
      client.setQueryData(["meeting", meeting.id], data.meeting);
      setConfirm(false);
      await refresh();
    } catch (e) {
      setError(message(e));
      await refresh();
    } finally {
      setBusy(false);
    }
  }
  async function respond(action: "accept" | "decline") {
    if (!state?.offer) return;
    setBusy(true);
    setError("");
    try {
      const params = {
        params: { path: { offer_id: state.offer.id } },
        body: { term_version: state.term_version },
      };
      unwrap(
        action === "accept"
          ? await api.POST("/api/v1/offers/{offer_id}/accept", params)
          : await api.POST("/api/v1/offers/{offer_id}/decline", params),
      );
      setConfirm(false);
      await refresh();
    } catch (e) {
      setError(message(e));
      await refresh();
    } finally {
      setBusy(false);
    }
  }
  const closed =
    meeting.status !== "scheduled" || (state && !state.can_declare);
  const allocated = state?.declaration === "going";
  const label =
    !state || !allocated
      ? state?.declaration === "not-going" || state?.declaration === "withdrawn"
        ? "Nie będziesz na tym spotkaniu"
        : "Grasz z nami?"
      : state.needs_reconfirmation
        ? "Potwierdź udział w nowym terminie"
        : state.allocation === "seat"
          ? "Masz miejsce na boisku"
          : state.offer?.state === "pending"
            ? "Mamy dla Ciebie wolne miejsce"
            : state.allocation === "reserved"
              ? "Miejsce czeka na propozycję organizatora"
              : `Jesteś na rezerwie · miejsce ${state.position ?? "—"}`;
  return (
    <section className="participation-card" aria-label="Twój udział">
      <div className="participation-title">
        <span className="empty-icon">
          {state?.allocation === "seat" ? (
            <Check />
          ) : state?.allocation === "reserved" ||
            state?.allocation === "waitlist" ? (
            <Clock3 />
          ) : (
            <UserPlus />
          )}
        </span>
        <div>
          <h3>{label}</h3>
          <p>
            {meeting.free_count} wolnych · {meeting.reserved_count}{" "}
            zarezerwowanych · limit {meeting.capacity}
          </p>
        </div>
      </div>
      {own.isPending && meeting.persisted ? (
        <p role="status">Sprawdzamy Twój zapis…</p>
      ) : own.isError ? (
        <div role="alert">
          <p>Nie udało się odświeżyć Twojego zapisu.</p>
          <button className="button" onClick={() => void own.refetch()}>
            Ponów
          </button>
        </div>
      ) : closed ? (
        <p className="form-note">Deklaracje na to spotkanie są zamknięte.</p>
      ) : (
        <>
          {state?.offer?.state === "pending" ? (
            <>
              <p className="form-note">
                Potwierdź udział w aktualnym terminie:{" "}
                {dateLabel(meeting.starts_at, meeting.timezone)},{" "}
                {hour(meeting.starts_at, meeting.timezone)}. Dopiero wtedy
                trafisz do uczestników.
              </p>
              <div className="participation-actions">
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => void respond("accept")}
                >
                  Przyjmuję miejsce
                </button>
                <button
                  className="button"
                  disabled={busy}
                  onClick={() => void respond("decline")}
                >
                  Odrzucam propozycję
                </button>
              </div>
            </>
          ) : (
            <div className="participation-actions">
              {state?.needs_reconfirmation && (
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => void declare("going")}
                >
                  Potwierdzam nowy termin
                </button>
              )}
              {!allocated && (
                <button
                  className="button declaration-going"
                  disabled={busy}
                  onClick={() => void declare("going")}
                >
                  Będę <Check size={17} aria-hidden="true" />
                </button>
              )}
              {state?.declaration !== "not-going" && (
                <button
                  className={
                    allocated ? "button" : "button declaration-not-going"
                  }
                  disabled={busy}
                  onClickCapture={(event) => event.currentTarget.focus()}
                  onClick={() =>
                    allocated ? setConfirm(true) : void declare("not-going")
                  }
                >
                  {allocated ? "Rezygnuję" : "Nie będę"}
                  {!allocated && <X size={17} aria-hidden="true" />}
                </button>
              )}
            </div>
          )}
          {state?.allocation === "reserved" &&
            state.offer?.state === "reserved" && (
              <p className="form-note">
                Organizator przekaże propozycję przez Messenger. Na razie nie
                jesteś potwierdzonym uczestnikiem.
              </p>
            )}
          {confirm && (
            <ConfirmDialog
              title="Potwierdzić rezygnację?"
              busy={busy}
              onDismiss={() => setConfirm(false)}
            >
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
              <p>
                {state?.cancellation_kind === "late"
                  ? "Do gry zostało mniej niż 24 godziny. W prywatnej historii zostanie późna rezygnacja."
                  : state?.cancellation_kind === "late_offer_exception"
                    ? "Miejsce przyjęto z rezerwy w ostatnich 24 godzinach. Ta rezygnacja nie będzie oznaczona jako późna."
                    : state?.cancellation_kind === "normal"
                      ? "Zgłaszasz rezygnację co najmniej 24 godziny przed grą."
                      : "Wycofasz zgłoszenie na ten termin, bez oznaczenia nieobecności."}
              </p>
              <div className="participation-actions">
                <button
                  className="button"
                  disabled={busy}
                  onClick={() => setConfirm(false)}
                >
                  Zostaję
                </button>
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => void declare("not-going")}
                >
                  Potwierdzam rezygnację
                </button>
              </div>
            </ConfirmDialog>
          )}
          <p className="participation-deadline">
            Zwykła rezygnacja do{" "}
            {dateLabel(
              state?.deadline ??
                new Date(
                  new Date(meeting.starts_at).getTime() - 86400000,
                ).toISOString(),
              meeting.timezone,
            )}
            ,{" "}
            {hour(
              state?.deadline ??
                new Date(
                  new Date(meeting.starts_at).getTime() - 86400000,
                ).toISOString(),
              meeting.timezone,
            )}
            .
          </p>
        </>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
