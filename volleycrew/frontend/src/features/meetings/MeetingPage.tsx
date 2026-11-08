import { useAdminView } from "../auth/ViewMode";
import { ResultCard } from "../results/ResultCard";
import { RoomPanel } from "../room/RoomPanel";
import { ConfirmedCourt } from "../room/Court";
import { MeetingActions } from "../schedule/MeetingActions";
import { ParticipationCard } from "./ParticipationCard";
import { OfferManager } from "./OfferManager";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Clock3,
  MapPin,
  UsersRound,
  Volleyball,
} from "lucide-react";
import { api, unwrap } from "../../lib/api/client";
import { dateLabel, hour, localDate, statusLabel } from "./dates";
import { useOpenMeeting } from "./useOpenMeeting";
import type { components } from "../../lib/api/schema";

type Detail = components["schemas"]["MeetingDetail"];
function Roster({
  title,
  players,
}: {
  title: string;
  players: Detail["participants"];
}) {
  return (
    <section className="card">
      <div className="section-title">
        <h2>{title}</h2>
        <span className="count-badge">{players.length}</span>
      </div>
      {players.length ? (
        <ol className="meeting-roster">
          {players.map((player) => (
            <li key={player.id}>
              <span className="profile-initial">{player.first_name[0]}</span>
              <span>
                {player.first_name} {player.last_name}
                {player.nickname ? <small>{player.nickname}</small> : null}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <div className="empty-state">
          <UsersRound size={28} strokeWidth={1.4} />
          <h3>
            {title === "Uczestnicy"
              ? "Ekipa jeszcze się zbiera"
              : "Rezerwa jest pusta"}
          </h3>
          <p>
            {title === "Uczestnicy"
              ? "Nie ma jeszcze potwierdzonych uczestników tego spotkania."
              : "Tutaj pojawią się osoby oczekujące na wolne miejsce."}
          </p>
        </div>
      )}
    </section>
  );
}

export function MeetingPage() {
  const adminView = useAdminView();
  const { id } = useParams();
  const opener = useOpenMeeting();
  const meeting = useQuery({
    queryKey: id ? ["meeting", id] : ["next-meeting"],
    queryFn: async ({ signal }) =>
      id
        ? unwrap(
            await api.GET("/api/v1/meetings/{meeting_id}", {
              params: { path: { meeting_id: id } },
              signal,
            }),
          )
        : unwrap(await api.GET("/api/v1/meetings/next", { signal })),
    refetchInterval: 30_000,
  });
  const item = meeting.data;
  return (
    <>
      {id && (
        <Link
          to={
            item
              ? `/calendar?month=${localDate(item.starts_at).slice(0, 7)}`
              : "/calendar"
          }
          className="text-link back-link"
        >
          <ArrowLeft size={16} /> Wróć do kalendarza
        </Link>
      )}
      <div className="page-heading">
        <h1>{id ? "Spotkanie" : "Najbliższe spotkanie"}</h1>
      </div>
      {meeting.isPending ? (
        <section className="card" role="status">
          Wczytujemy spotkanie…
        </section>
      ) : !item && meeting.isError ? (
        <section className="card" role="alert">
          <h2>Nie udało się wczytać spotkania</h2>
          <p className="form-note">
            Sprawdź połączenie lub wróć do kalendarza.
          </p>
          <button className="button" onClick={() => void meeting.refetch()}>
            Spróbuj ponownie
          </button>
        </section>
      ) : !item ? (
        <section className="card empty-state">
          <CalendarDays size={36} />
          <h2>Nie ma kolejnego spotkania</h2>
          <p>Gdy pojawi się nowy termin, zobaczysz go tutaj.</p>
          <Link to="/calendar" className="text-link">
            Otwórz kalendarz <ArrowRight size={15} />
          </Link>
        </section>
      ) : (
        <>
          {meeting.isError && (
            <p role="alert" className="form-error">
              Nie udało się odświeżyć danych. Pokazujemy ostatnio pobrany
              termin.{" "}
              <button
                className="button small"
                onClick={() => void meeting.refetch()}
              >
                Ponów
              </button>
            </p>
          )}
          <div className="dashboard">
            <div className="main-column">
              <section
                className={`meeting-card ${item.status === "cancelled" ? "meeting-cancelled" : ""}`}
              >
                <div className="hero">
                  <div className="hero-copy">
                    <span className="eyebrow">
                      <span className="live-dot" /> CZAS NA WSPÓLNĄ GRĘ
                    </span>
                    <h2 className="hero-date">
                      <time dateTime={item.starts_at}>
                        {dateLabel(item.starts_at, item.timezone)}
                      </time>
                    </h2>
                    <p>
                      <Clock3 size={16} />
                      {hour(item.starts_at, item.timezone)} —{" "}
                      {hour(item.ends_at, item.timezone)}
                    </p>
                    <p>
                      <MapPin size={16} />
                      {item.venue}
                    </p>
                  </div>
                  <div className="court-illustration" aria-hidden="true">
                    <div className="mini-court">
                      <i />
                      <i />
                    </div>
                    <Volleyball className="hero-ball" strokeWidth={1} />
                  </div>
                </div>
                {item.previous_starts_at && item.status !== "cancelled" && (
                  <div className="term-change-banner">
                    <strong>Termin spotkania został zmieniony</strong>
                    <p>
                      Poprzednio: {dateLabel(item.previous_starts_at)},{" "}
                      {hour(item.previous_starts_at)}.
                    </p>
                    <p>
                      Teraz: {dateLabel(item.starts_at)}, {hour(item.starts_at)}
                      .
                    </p>
                  </div>
                )}
                <div className="meeting-meta">
                  <span className={`meeting-state ${item.status}`}>
                    {statusLabel[item.status]}
                  </span>
                  <span>
                    {item.participant_count} / {item.capacity} uczestników
                  </span>
                </div>
                {item.status === "cancelled" ? (
                  <p className="meeting-message">
                    Spotkanie zostało odwołane. Nie powoduje oznaczeń
                    nieobecności.
                  </p>
                ) : item.status === "completed" ? (
                  <p className="meeting-message">
                    To spotkanie jest już zakończone.
                  </p>
                ) : (
                  <ParticipationCard key={item.id} meeting={item} />
                )}
              </section>
              {adminView && item.persisted && item.status === "scheduled" && (
                <OfferManager
                  meetingId={item.id}
                  termVersion={item.term_version}
                />
              )}
              {adminView && item.persisted && (
                <MeetingActions key={item.id} meeting={item} />
              )}
              {item.persisted &&
                item.status !== "cancelled" &&
                (adminView ? (
                  <RoomPanel key={`room-${item.id}`} meetingId={item.id} />
                ) : (
                  <ConfirmedCourt
                    key={`court-${item.id}`}
                    meetingId={item.id}
                  />
                ))}
              {item.persisted && item.status === "completed" && !adminView && (
                <ResultCard meetingId={item.id} />
              )}
              {!!item.awaiting_confirmation.length && (
                <Roster
                  title="Oczekują na potwierdzenie"
                  players={item.awaiting_confirmation}
                />
              )}
              <Roster title="Uczestnicy" players={item.participants} />
              {item.status !== "completed" && (
                <Roster title="Rezerwa" players={item.waitlist} />
              )}
            </div>
            <aside className="right-column">
              <section className="card upcoming">
                <div className="section-title">
                  <h2>Zaplanuj kolejną grę</h2>
                  <CalendarDays size={19} />
                </div>
                <p>
                  Sprawdź terminy na kolejne miesiące i znajdź czas dla ekipy.
                </p>
                <Link className="text-link" to="/calendar">
                  Otwórz kalendarz <ArrowRight size={15} />
                </Link>
              </section>
              {!id && !item.persisted && (
                <section className="card">
                  <h2>Ten termin</h2>
                  <p className="form-note">
                    Otwórz szczegóły spotkania. Samo otwarcie nie zapisuje Cię
                    na grę.
                  </p>
                  <button
                    className="button primary"
                    disabled={!!opener.busy}
                    onClick={() => void opener.open(item)}
                  >
                    Otwórz spotkanie <ArrowRight size={16} />
                  </button>
                  {opener.error && (
                    <p className="form-error" role="alert">
                      {opener.error}
                    </p>
                  )}
                </section>
              )}
            </aside>
          </div>
        </>
      )}
    </>
  );
}
