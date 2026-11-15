import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { KeyRound, LoaderCircle, ShieldCheck, Volleyball } from "lucide-react";
import { api, message, unwrap } from "../../lib/api/client";
import { PreviewProfiles } from "./PreviewProfiles";
import { useSession } from "./useSession";
import { useAdminView } from "./ViewMode";
import { rememberedUsername, rememberUsername } from "./rememberedUsername";
import { useAuthLinkToken } from "./useAuthLinkToken";
import { GoogleLogin, GoogleNotice } from "./GoogleAuth";
import { UsernameField, PasswordField } from "./CredentialFields";
import { InstallApp } from "../install/InstallApp";

export function Protected({
  children,
  admin = false,
}: {
  children: ReactNode;
  admin?: boolean;
}) {
  const session = useSession();
  const location = useLocation();
  const adminView = useAdminView();
  if (session.isPending)
    return (
      <div className="auth-loading" role="status">
        Sprawdzamy Twoją sesję…
      </div>
    );
  if (session.isError && !session.data)
    return (
      <div className="auth-loading" role="alert">
        <p>Nie udało się połączyć z usługą.</p>
        <button className="button" onClick={() => void session.refetch()}>
          Spróbuj ponownie
        </button>
      </div>
    );
  if (!session.data)
    return (
      <Navigate
        to="/login"
        replace
        state={{ returnTo: location.pathname + location.search }}
      />
    );
  if (admin && !adminView)
    return (
      <div className="card" role="alert">
        <h1>Brak dostępu</h1>
        <p>Ten widok jest dostępny tylko dla organizatora.</p>
        <Link className="text-link" to="/">
          Wróć do spotkania
        </Link>
      </div>
    );
  return children;
}

function AuthCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  useEffect(() => {
    document.title = `Volleycrew · ${title}`;
  }, [title]);
  return (
    <main className="auth-layout">
      <section className="card auth-card">
        <div className="auth-emblem">
          <Volleyball size={30} />
        </div>
        <h1>{title}</h1>
        <p className="auth-subtitle">{subtitle}</p>
        {children}
        <InstallApp />
      </section>
    </main>
  );
}

function Pending({ busy, children }: { busy: boolean; children: ReactNode }) {
  return (
    <button className="button primary wide" type="submit" disabled={busy}>
      {busy ? (
        <>
          <LoaderCircle size={17} className="spin" /> Chwila…
        </>
      ) : (
        children
      )}
    </button>
  );
}

export function LoginPage({ preview = false }: { preview?: boolean }) {
  const session = useSession();
  const [username, setUsername] = useState(rememberedUsername);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const client = useQueryClient(),
    navigate = useNavigate();
  const location = useLocation();
  const requested = location.state?.returnTo;
  const destination =
    typeof requested === "string" &&
    requested.startsWith("/") &&
    !requested.startsWith("//") &&
    !requested.startsWith("/login")
      ? requested
      : "/";
  if (session.data && !preview) return <Navigate to={destination} replace />;
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const user = unwrap(
        await api.POST("/api/v1/auth/login", { body: { username, password } }),
      );
      await client.cancelQueries();
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "me",
      });
      rememberUsername(user.username ?? "");
      client.setQueryData(["me"], user);
      setPassword("");
      navigate(destination, { replace: true });
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthCard title="Dobrze Cię widzieć" subtitle="Podaj swój login i hasło.">
      <GoogleNotice />
      {!preview && <GoogleLogin destination={destination} />}
      {!preview && <PreviewProfiles />}
      <form onSubmit={(e) => void submit(e)}>
        <UsernameField
          value={username}
          onChange={setUsername}
          disabled={busy}
        />
        <PasswordField
          label="Hasło"
          value={password}
          onChange={setPassword}
          disabled={busy}
        />
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <Pending busy={busy}>
          Wejdź na boisko <KeyRound size={17} />
        </Pending>
        <p className="form-note">
          Nie pamiętasz loginu lub hasła? Organizator może przekazać Ci
          jednorazowy link do ustawienia nowych danych dostępu.
        </p>
      </form>
      <div className="auth-footnote">
        <ShieldCheck size={15} /> Sesja zostanie zapamiętana na tym urządzeniu.
      </div>
    </AuthCard>
  );
}

export function RegisterPage({ bootstrap = false }: { bootstrap?: boolean }) {
  const token = useAuthLinkToken();
  const [firstName, setFirstName] = useState(bootstrap ? "Arkadiusz" : "");
  const [lastName, setLastName] = useState(bootstrap ? "Dalecki" : "");
  const [nickname, setNickname] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const client = useQueryClient(),
    navigate = useNavigate();
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (password !== repeat) {
      setError("Podane hasła muszą być takie same.");
      return;
    }
    setBusy(true);
    try {
      const body = {
        token,
        first_name: firstName,
        last_name: lastName,
        nickname: nickname || null,
        username,
        password,
      };
      const user = unwrap(
        bootstrap
          ? await api.POST("/api/v1/auth/bootstrap", { body })
          : await api.POST("/api/v1/auth/register", { body }),
      );
      await client.cancelQueries();
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "me",
      });
      rememberUsername(user.username ?? "");
      client.setQueryData(["me"], user);
      setPassword("");
      setRepeat("");
      navigate("/", { replace: true });
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthCard
      title={bootstrap ? "Pierwszy organizator" : "Dołącz do ekipy"}
      subtitle={
        bootstrap
          ? "Ustaw login i hasło organizatora. Istniejący profil zachowa swoje dane."
          : "Zaproszenie otwiera drzwi do naszej ekipy."
      }
    >
      {!token ? (
        <p role="alert" className="form-error">
          Otwórz ponownie pełny link przekazany przez organizatora. Ze względów
          bezpieczeństwa odświeżenie strony wymaga ponownego otwarcia linku.
        </p>
      ) : (
        <form onSubmit={(e) => void submit(e)}>
          <div className="form-row">
            <label className="form-field">
              Imię
              <input
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                autoComplete="given-name"
                maxLength={80}
                required
                disabled={busy}
              />
            </label>
            <label className="form-field">
              Nazwisko
              <input
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                autoComplete="family-name"
                maxLength={80}
                required
                disabled={busy}
              />
            </label>
          </div>
          <label className="form-field">
            Przydomek (opcjonalnie)
            <input
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              autoComplete="nickname"
              maxLength={40}
              disabled={busy}
            />
            <small>Pomoże odróżnić osoby o tym samym imieniu i nazwisku.</small>
          </label>
          <UsernameField
            value={username}
            onChange={setUsername}
            disabled={busy}
          />
          <PasswordField
            label="Twoje hasło"
            value={password}
            onChange={setPassword}
            fresh
            disabled={busy}
          />
          <PasswordField
            label="Powtórz hasło"
            value={repeat}
            onChange={setRepeat}
            fresh
            disabled={busy}
          />
          <p className="form-note">
            Imię i nazwisko będą używane na liście podpisów dla szkoły. Login i
            przydomek nie trafią na wydruk.
          </p>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <Pending busy={busy}>
            {bootstrap ? "Ustaw dostęp organizatora" : "Dołączam do gry"}
          </Pending>
        </form>
      )}
      <Link className="text-link" to="/login">
        Mam już profil — zaloguj się
      </Link>
    </AuthCard>
  );
}

export function ResetPasswordPage() {
  const token = useAuthLinkToken();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const client = useQueryClient(),
    navigate = useNavigate();
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (password !== repeat) {
      setError("Podane hasła muszą być takie same.");
      return;
    }
    setBusy(true);
    try {
      const user = unwrap(
        await api.POST("/api/v1/auth/reset-password", {
          body: { token, username, password },
        }),
      );
      await client.cancelQueries();
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "me",
      });
      rememberUsername(user.username ?? "");
      client.setQueryData(["me"], user);
      setPassword("");
      setRepeat("");
      navigate("/", { replace: true });
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthCard
      title="Nowe hasło, ta sama ekipa"
      subtitle="Link jest jednorazowy i działa przez 30 minut. Możesz zachować dotychczasowy login lub wybrać nowy."
    >
      {!token ? (
        <p className="form-error" role="alert">
          Otwórz ponownie pełny link do resetu hasła. Ze względów bezpieczeństwa
          odświeżenie strony wymaga ponownego otwarcia linku.
        </p>
      ) : (
        <form onSubmit={(e) => void submit(e)}>
          <UsernameField
            value={username}
            onChange={setUsername}
            disabled={busy}
          />
          <PasswordField
            label="Nowe hasło"
            value={password}
            onChange={setPassword}
            fresh
            disabled={busy}
          />
          <PasswordField
            label="Powtórz nowe hasło"
            value={repeat}
            onChange={setRepeat}
            fresh
            disabled={busy}
          />
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <Pending busy={busy}>Ustaw nowe hasło</Pending>
        </form>
      )}
    </AuthCard>
  );
}
