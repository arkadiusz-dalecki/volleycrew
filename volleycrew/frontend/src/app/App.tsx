import { PreviewProfiles } from "../features/auth/PreviewProfiles";
import { AppEnvironment, ConnectionNotice } from "../components/AppEnvironment";
import {
  RankingPage,
  RatingHistoryPage,
} from "../features/results/RankingPage";
import { SignatureListPage } from "../features/documents/SignatureList";
import { PlayerHistoryPage } from "../features/room/HistoryPanel";
import { MeetingPage } from "../features/meetings/MeetingPage";
import { CalendarPage } from "../features/meetings/CalendarPage";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, message, unwrap } from "../lib/api/client";
import {
  LoginPage,
  RegisterPage,
  ResetPinPage,
  Protected,
} from "../features/auth/AuthPages";
import { ProfilePage } from "../features/auth/ProfilePage";
import { AdminSettings } from "../features/auth/AdminSettings";
import { useSession } from "../features/auth/useSession";
import { NavLink, Route, Routes, useLocation, Link } from "react-router-dom";
import {
  CalendarDays,
  House,
  Trophy,
  UserRound,
  Volleyball,
  MapPin,
  ArrowRight,
  Settings,
  LogOut,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { dateLabel, hour } from "../features/meetings/dates";
import { ServiceStatus } from "../features/system/ServiceStatus";

const navigation: { path: string; label: string; icon: LucideIcon }[] = [
  { path: "/", label: "Spotkanie", icon: House },
  { path: "/calendar", label: "Kalendarz", icon: CalendarDays },
  { path: "/ranking", label: "Ranking", icon: Trophy },
  { path: "/profile", label: "Mój profil", icon: UserRound },
];

function Navigation({ mobile = false }: { mobile?: boolean }) {
  return (
    <nav
      className={mobile ? "mobile-nav" : "side-nav"}
      aria-label={mobile ? "Nawigacja mobilna" : "Menu główne"}
    >
      {navigation.map(({ path, label, icon: Icon }) => (
        <NavLink to={path} end={path === "/"} key={path}>
          <Icon size={20} />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <Link to="/" className="brand" aria-label="Volleycrew — strona główna">
      <Volleyball size={33} strokeWidth={1.6} />
      volleycrew<span>.</span>
    </Link>
  );
}

function EmptyPage({
  title,
  description,
  icon: Icon,
  heading,
  text,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  heading: string;
  text: string;
}) {
  return (
    <>
      <div className="page-heading">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <section className="card full-page-empty">
        <div className="empty-state">
          <Icon size={38} strokeWidth={1.3} />
          <h2>{heading}</h2>
          <p>{text}</p>
          <Link className="text-link" to="/">
            Wróć do spotkania <ArrowRight size={15} />
          </Link>
        </div>
      </section>
    </>
  );
}

function PrivateApp() {
  const next = useQuery({
    queryKey: ["next-meeting"],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/api/v1/meetings/next", { signal })),
    refetchInterval: 30_000,
  });
  const session = useSession();
  const client = useQueryClient();
  const [logoutError, setLogoutError] = useState("");
  const [busy, setBusy] = useState(false);
  async function logout() {
    setBusy(true);
    setLogoutError("");
    try {
      unwrap(await api.POST("/api/v1/auth/logout"));
      await client.cancelQueries();
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "me",
      });
      client.setQueryData(["me"], null);
    } catch (e) {
      setLogoutError(message(e));
    } finally {
      setBusy(false);
    }
  }
  const location = useLocation();
  const current = navigation.find((item) => item.path === location.pathname);
  return (
    <div className="app-shell">
      <AppEnvironment />
      <a className="skip-link" href="#main">
        Przejdź do treści
      </a>
      <aside className="sidebar">
        <Brand />
        <p className="nav-caption">TWOJA EKIPA</p>
        <Navigation />
        {session.data?.role === "admin" && (
          <Link className="admin-link" to="/admin/settings">
            <Settings size={18} /> Ustawienia ekipy
          </Link>
        )}
        <div className="sidebar-bottom">
          <div className="venue">
            <MapPin size={20} />
            <span>Najbliższe spotkanie</span>
            {next.data ? (
              <>
                <strong>
                  <time dateTime={next.data.starts_at}>
                    {dateLabel(next.data.starts_at, next.data.timezone)}
                  </time>
                </strong>
                <span>
                  {hour(next.data.starts_at, next.data.timezone)} —{" "}
                  {hour(next.data.ends_at, next.data.timezone)}
                </span>
              </>
            ) : (
              <strong>
                {next.isPending
                  ? "Wczytujemy termin…"
                  : next.isError
                    ? "Nie udało się pobrać terminu"
                    : "Brak kolejnego spotkania"}
              </strong>
            )}
            {next.isError && (
              <button
                className="button small"
                onClick={() => void next.refetch()}
              >
                Ponów
              </button>
            )}
            <Link className="text-link" to="/calendar">
              Terminy w kalendarzu
            </Link>
          </div>
          <p className="sidebar-signoff">MEET · PLAY · REPEAT</p>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="mobile-brand">
            <Brand />
          </div>
          <div className="breadcrumb">
            Twoja ekipa <ArrowRight size={13} />
            <span>
              {current?.label ??
                (location.pathname.startsWith("/meetings/")
                  ? "Spotkanie"
                  : location.pathname.startsWith("/ranking/")
                    ? "Ranking"
                    : location.pathname.startsWith("/admin/")
                      ? "Ustawienia ekipy"
                      : "Nie znaleziono strony")}
            </span>
          </div>
          <div className="header-actions">
            <span className="header-note">{session.data?.first_name}</span>
            <button
              className="button small"
              onClick={() => void logout()}
              disabled={busy}
            >
              <LogOut size={16} />
              <span>Wyloguj</span>
            </button>
          </div>
        </header>
        <main id="main" className="content" tabIndex={-1}>
          <ConnectionNotice />
          <PreviewProfiles />
          {logoutError && (
            <p role="alert" className="form-error">
              {logoutError}
            </p>
          )}
          <Routes>
            <Route
              path="/admin/meetings/:meetingId/signature-list"
              element={
                <Protected admin>
                  <SignatureListPage />
                </Protected>
              }
            />
            <Route path="/" element={<MeetingPage />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/meetings/:id" element={<MeetingPage />} />
            <Route path="/ranking" element={<RankingPage />} />
            <Route
              path="/ranking/players/:playerId"
              element={<RatingHistoryPage />}
            />
            <Route
              path="/admin/players/:playerId/history"
              element={
                <Protected admin>
                  <PlayerHistoryPage />
                </Protected>
              }
            />
            <Route path="/profile" element={<ProfilePage />} />
            <Route
              path="/admin/settings"
              element={
                <Protected admin>
                  <AdminSettings />
                </Protected>
              }
            />
            <Route
              path="*"
              element={
                <EmptyPage
                  title="Nie znaleziono strony"
                  description="Ten adres nie prowadzi do żadnego widoku."
                  icon={Volleyball}
                  heading="Wróćmy na boisko"
                  text="Wybierz jedną z zakładek albo wróć do najbliższego spotkania."
                />
              }
            />
          </Routes>
          <footer className="app-footer">
            <span>VOLLEYCREW · GRAMY RAZEM</span>
            <ServiceStatus />
          </footer>
        </main>
      </div>
      <Navigation mobile />
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      {import.meta.env.DEV && (
        <Route path="/preview/login" element={<LoginPage preview />} />
      )}
      <Route path="/join" element={<RegisterPage key="join" />} />
      <Route path="/join/:token" element={<RegisterPage key="join-legacy" />} />
      <Route path="/setup" element={<RegisterPage bootstrap key="setup" />} />
      <Route path="/reset-pin" element={<ResetPinPage />} />
      <Route path="/reset-pin/:token" element={<ResetPinPage />} />
      <Route
        path="*"
        element={
          <Protected>
            <PrivateApp />
          </Protected>
        }
      />
    </Routes>
  );
}
