import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import { KeyRound, LoaderCircle, ShieldCheck, Volleyball } from "lucide-react";
import { api, message, unwrap } from "../../lib/api/client";
import { useSession } from "./useSession";

export function Protected({
  children,
  admin = false,
}: {
  children: ReactNode;
  admin?: boolean;
}) {
  const session = useSession();
  const location = useLocation();
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
  if (admin && session.data.role !== "admin")
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

export function LoginPage() {
  const session = useSession();
  const profiles = useQuery({
    queryKey: ["login-profiles"],
    queryFn: async () => unwrap(await api.GET("/api/v1/auth/profiles")),
    staleTime: 0,
  });
  const [profile, setProfile] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const requested = location.state?.returnTo;
  const destination =
    typeof requested === "string" &&
    requested.startsWith("/") &&
    !requested.startsWith("//") &&
    !requested.startsWith("/login")
      ? requested
      : "/";
  if (session.data) return <Navigate to={destination} replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const user = unwrap(
        await api.POST("/api/v1/auth/login", {
          body: { profile_id: profile, pin },
        }),
      );
      client.setQueryData(["me"], user);
      setPin("");
      navigate(destination, { replace: true });
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Dobrze Cię widzieć"
      subtitle="Wybierz swój profil i podaj sześciocyfrowy PIN."
    >
      {profiles.isPending ? (
        <p role="status">Wczytujemy profile…</p>
      ) : profiles.isError ? (
        <div role="alert">
          <p>Nie udało się pobrać listy.</p>
          <button className="button" onClick={() => void profiles.refetch()}>
            Ponów
          </button>
        </div>
      ) : !profiles.data?.length ? (
        <p className="form-note">
          Nie ma jeszcze dostępnych profili. Poproś organizatora o link z
          zaproszeniem.
        </p>
      ) : (
        <form onSubmit={(e) => void submit(e)}>
          <fieldset className="profile-picker" disabled={busy}>
            <legend>Twój profil</legend>
            <div className="profile-options">
              {profiles.data.map((item) => (
                <label
                  className={`profile-option ${profile === item.profile_id ? "selected" : ""}`}
                  key={item.profile_id}
                >
                  <input
                    type="radio"
                    name="profile"
                    value={item.profile_id}
                    required
                    checked={profile === item.profile_id}
                    onChange={() => setProfile(item.profile_id)}
                  />
                  <span className="profile-initial">{item.first_name[0]}</span>
                  <span>
                    {item.first_name} {item.masked_last_name}
                    {item.nickname ? ` — ${item.nickname}` : ""}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <label className="form-field">
            PIN
            <input
              type="password"
              inputMode="numeric"
              autoComplete="current-password"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              pattern="[0-9]{6}"
              minLength={6}
              maxLength={6}
              required
              disabled={busy}
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <Pending busy={busy}>
            Wejdź na boisko <KeyRound size={17} />
          </Pending>
          <p className="form-note">
            Nie pamiętasz PIN-u? Organizator może przekazać Ci jednorazowy link
            do ustawienia nowego.
          </p>
        </form>
      )}
      <div className="auth-footnote">
        <ShieldCheck size={15} /> Profil zostanie zapamiętany na tym urządzeniu.
      </div>
    </AuthCard>
  );
}

export function RegisterPage({ bootstrap = false }: { bootstrap?: boolean }) {
  const location = useLocation(),
    params = useParams();
  const token = location.hash.slice(1) || params.token || "";
  const [firstName, setFirstName] = useState(bootstrap ? "Arkadiusz" : "");
  const [lastName, setLastName] = useState(bootstrap ? "Dalecki" : "");
  const [nickname, setNickname] = useState("");
  const [pin, setPin] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const client = useQueryClient(),
    navigate = useNavigate();
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (pin !== repeat) {
      setError("Podane PIN-y muszą być takie same.");
      return;
    }
    setBusy(true);
    try {
      const body = {
        token,
        first_name: firstName,
        last_name: lastName,
        nickname: nickname || null,
        pin,
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
      client.setQueryData(["me"], user);
      setPin("");
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
      title={bootstrap ? "Twoja ekipa zaczyna tutaj" : "Dołącz do ekipy"}
      subtitle={
        bootstrap
          ? "Utwórz profil organizatora i ustaw własny PIN."
          : "Załóż swój profil z zaproszenia. Resztę załatwimy na boisku."
      }
    >
      {!token ? (
        <p role="alert" className="form-error">
          Otwórz pełny link przekazany przez organizatora.
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
          <div className="form-row">
            <label className="form-field">
              Twój PIN
              <input
                type="password"
                inputMode="numeric"
                autoComplete="new-password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                pattern="[0-9]{6}"
                minLength={6}
                maxLength={6}
                required
                disabled={busy}
              />
            </label>
            <label className="form-field">
              Powtórz PIN
              <input
                type="password"
                inputMode="numeric"
                autoComplete="new-password"
                value={repeat}
                onChange={(e) => setRepeat(e.target.value)}
                pattern="[0-9]{6}"
                minLength={6}
                maxLength={6}
                required
                disabled={busy}
              />
            </label>
          </div>
          <p className="form-note">
            Imię i nazwisko będą używane na liście podpisów dla szkoły.
            Przydomek nie trafi na wydruk.
          </p>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <Pending busy={busy}>
            {bootstrap ? "Utwórz profil organizatora" : "Dołączam do gry"}
          </Pending>
        </form>
      )}
      <Link className="text-link" to="/login">
        Mam już profil — zaloguj się
      </Link>
    </AuthCard>
  );
}

export function ResetPinPage() {
  const location = useLocation(),
    params = useParams();
  const token = location.hash.slice(1) || params.token || "";
  const [pin, setPin] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const client = useQueryClient(),
    navigate = useNavigate();
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (pin !== repeat) {
      setError("Podane PIN-y muszą być takie same.");
      return;
    }
    setBusy(true);
    try {
      const user = unwrap(
        await api.POST("/api/v1/auth/reset-pin", { body: { token, pin } }),
      );
      await client.cancelQueries();
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "me",
      });
      client.setQueryData(["me"], user);
      setPin("");
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
      title="Nowy PIN, ta sama ekipa"
      subtitle="Link jest jednorazowy i działa przez 30 minut."
    >
      {!token ? (
        <p className="form-error" role="alert">
          Brakuje pełnego linku do resetu PIN-u.
        </p>
      ) : (
        <form onSubmit={(e) => void submit(e)}>
          <label className="form-field">
            Nowy PIN
            <input
              type="password"
              inputMode="numeric"
              autoComplete="new-password"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              pattern="[0-9]{6}"
              minLength={6}
              maxLength={6}
              required
              disabled={busy}
            />
          </label>
          <label className="form-field">
            Powtórz nowy PIN
            <input
              type="password"
              inputMode="numeric"
              autoComplete="new-password"
              value={repeat}
              onChange={(e) => setRepeat(e.target.value)}
              pattern="[0-9]{6}"
              minLength={6}
              maxLength={6}
              required
              disabled={busy}
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <Pending busy={busy}>Ustaw nowy PIN</Pending>
        </form>
      )}
    </AuthCard>
  );
}
