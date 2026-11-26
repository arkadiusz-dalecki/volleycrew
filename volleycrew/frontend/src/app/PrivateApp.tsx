import { ViewModeSwitch, useAdminView } from "../features/auth/ViewMode";
import { InstallApp } from "../features/install/InstallApp";
import { PreviewProfiles } from "../features/auth/PreviewProfiles";
import { AppEnvironment, ConnectionNotice } from "../components/AppEnvironment";
import { lazy, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, message, unwrap } from "../lib/api/client";
import { Protected } from "../features/auth/AuthPages";
import { useSession } from "../features/auth/useSession";
import { NavLink, Route, Routes, useLocation, Link } from "react-router-dom";
import {
  CalendarDays,
  CircleAlert,
  Wallet,
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
import { money } from "../features/settlements/money";
import { ServiceStatus } from "../features/system/ServiceStatus";

import { RouteContent } from "../components/RouteContent";
const SettlementsPage = lazy(() =>
  import("../features/settlements/SettlementsPage").then((module) => ({
    default: module.SettlementsPage,
  })),
);
const AdminSettlementsPage = lazy(() =>
  import("../features/settlements/SettlementsPage").then((module) => ({
    default: module.AdminSettlementsPage,
  })),
);
const MeetingPage = lazy(() =>
  import("../features/meetings/MeetingPage").then((module) => ({
    default: module.MeetingPage,
  })),
);
const CalendarPage = lazy(() =>
  import("../features/meetings/CalendarPage").then((module) => ({
    default: module.CalendarPage,
  })),
);
const RankingPage = lazy(() =>
  import("../features/results/RankingPage").then((module) => ({
    default: module.RankingPage,
  })),
);
const RatingHistoryPage = lazy(() =>
  import("../features/results/RankingPage").then((module) => ({
    default: module.RatingHistoryPage,
  })),
);
const ProfilePage = lazy(() =>
  import("../features/auth/ProfilePage").then((module) => ({
    default: module.ProfilePage,
  })),
);
const AdminSettings = lazy(() =>
  import("../features/auth/AdminSettings").then((module) => ({
    default: module.AdminSettings,
  })),
);
const SignatureListPage = lazy(() =>
  import("../features/documents/SignatureList").then((module) => ({
    default: module.SignatureListPage,
  })),
);
const PlayerHistoryPage = lazy(() =>
  import("../features/room/HistoryPanel").then((module) => ({
    default: module.PlayerHistoryPage,
  })),
);

const navigation: { path: string; label: string; icon: LucideIcon }[] = [
  { path: "/", label: "Spotkanie", icon: House },
  { path: "/calendar", label: "Kalendarz", icon: CalendarDays },
  { path: "/ranking", label: "Ranking", icon: Trophy },
  { path: "/settlements", label: "Rozliczenia", icon: Wallet },
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
          <Icon size={20} aria-hidden="true" />
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

function SettlementReminder({
  due,
  mobile = false,
}: {
  due: number;
  mobile?: boolean;
}) {
  return (
    <article
      className={`venue settlement-reminder${mobile ? " settlement-reminder-mobile" : ""}`}
    >
      <CircleAlert size={20} aria-hidden="true" />
      <span>Zaległe rozliczenia</span>
      <strong>{money(due)}</strong>
      <span>Do zapłaty</span>
      <Link className="text-link" to="/settlements">
        Przejdź do rozliczeń
      </Link>
    </article>
  );
}

export function PrivateApp() {
  const adminView = useAdminView();
  const next = useQuery({
    queryKey: ["next-meeting"],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/api/v1/meetings/next", { signal })),
    refetchInterval: 30_000,
  });
  const settlements = useQuery({
    queryKey: ["settlements", "mine"],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/api/v1/me/settlements", { signal })),
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
  const overdueAmount =
    settlements.data?.reminder && location.pathname !== "/settlements"
      ? settlements.data.due
      : null;
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
        {adminView && (
          <Link className="admin-link" to="/admin/settings">
            <Settings size={18} /> Ustawienia ekipy
          </Link>
        )}
        {adminView && (
          <Link className="admin-link" to="/admin/settlements">
            Rozliczenia ekipy
          </Link>
        )}
        <div className="sidebar-bottom">
          {overdueAmount !== null && <SettlementReminder due={overdueAmount} />}
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
                (location.pathname.endsWith("/settlements")
                  ? "Rozliczenia"
                  : location.pathname.startsWith("/meetings/")
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
          <ViewModeSwitch />
          <ConnectionNotice />
          {overdueAmount !== null && (
            <SettlementReminder due={overdueAmount} mobile />
          )}
          <PreviewProfiles />
          {logoutError && (
            <p role="alert" className="form-error">
              {logoutError}
            </p>
          )}
          <RouteContent>
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
              <Route path="/settlements" element={<SettlementsPage />} />
              <Route
                path="/admin/settlements"
                element={
                  <Protected admin>
                    <AdminSettlementsPage />
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
          </RouteContent>
          <footer className="app-footer">
            <span>VOLLEYCREW · GRAMY RAZEM</span>
            <ServiceStatus />
            <InstallApp />
          </footer>
        </main>
      </div>
      <Navigation mobile />
    </div>
  );
}
