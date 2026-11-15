import { useLayoutEffect, useState } from "react";
import type { FormEvent } from "react";
import { useLocation } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, message, unwrap } from "../../lib/api/client";
import { PasswordField } from "./CredentialFields";
import { basePath } from "../../lib/base";
import { useSession } from "./useSession";

function useGoogleConfig() {
  return useQuery({
    queryKey: ["google-config"],
    queryFn: async () => unwrap(await api.GET("/api/v1/auth/google/config")),
    staleTime: 60_000,
  });
}

const notices: Record<string, string> = {
  invite:
    "Zaproszenie jest nieaktywne. Poproś organizatora o nowy link do dołączenia.",
  limited:
    "Za dużo prób logowania Google. Odczekaj chwilę i rozpocznij logowanie ponownie.",
  linked: "Konto Google zostało połączone z Twoim profilem.",
  cancelled:
    "Logowanie Google zostało anulowane. Możesz spróbować ponownie lub użyć hasła.",
  invalid:
    "Nie udało się potwierdzić logowania Google. Rozpocznij je ponownie.",
  unavailable:
    "Google jest teraz niedostępne. Spróbuj ponownie lub zaloguj się hasłem.",
  unlinked:
    "To konto Google nie jest połączone z profilem. Dołącz przez link zaproszenia albo zaloguj się hasłem i połącz Google w swoim profilu.",
  conflict:
    "To konto Google lub profil ma już inne powiązanie. Zaloguj się hasłem, aby je sprawdzić.",
  session:
    "Sesja użyta do łączenia wygasła lub została zmieniona. Zaloguj się hasłem i spróbuj ponownie.",
};

export function GoogleNotice() {
  const location = useLocation();
  const [code] = useState(() =>
    location.hash.startsWith("#google=") ? location.hash.slice(8) : "",
  );
  useLayoutEffect(() => {
    if (window.location.hash.startsWith("#google=")) {
      window.history.replaceState(
        window.history.state,
        "",
        window.location.pathname + window.location.search,
      );
    }
  }, [location.key]);
  return notices[code] ? (
    <p className="form-notice" role="status">
      {notices[code]}
    </p>
  ) : null;
}

function GoogleLabel({ join = false }: { join?: boolean }) {
  return (
    <>
      <img src={`${basePath}/google-g.png`} alt="" width="20" height="20" />
      {join ? "Dołącz przez Google" : "Zaloguj przez Google"}
    </>
  );
}

function usePublicGoogle(publicUrl: string | undefined) {
  return Boolean(
    basePath ||
    (publicUrl && new URL(publicUrl).origin !== window.location.origin),
  );
}

export function GoogleLogin({ destination = "/" }: { destination?: string }) {
  const config = useGoogleConfig();
  const external = usePublicGoogle(config.data?.public_url);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!config.data?.enabled) return null;
  async function start() {
    setError("");
    setBusy(true);
    try {
      const result = unwrap(
        await api.POST("/api/v1/auth/google/start", {
          body: { mode: "login", return_to: destination },
        }),
      );
      window.location.assign(result.url);
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  }
  return (
    <div className="google-access">
      {external ? (
        <>
          <a
            className="google-button"
            href={`${config.data.public_url}/login`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <GoogleLabel />
          </a>
          <p className="form-note">
            Logowanie Google otworzy główny adres Volleycrew w nowej karcie.
            Sesja Home Assistant pozostaje osobna.
          </p>
        </>
      ) : (
        <button
          className="google-button"
          disabled={busy}
          onClick={() => void start()}
        >
          {busy ? "Łączymy z Google…" : <GoogleLabel />}
        </button>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function GoogleConnection() {
  const { data: me } = useSession();
  const config = useGoogleConfig();
  const connection = useQuery({
    queryKey: ["google-connection"],
    queryFn: async () => unwrap(await api.GET("/api/v1/me/google")),
  });
  const external = usePublicGoogle(config.data?.public_url);
  const client = useQueryClient();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  if (!config.data?.enabled && !connection.data?.connected) return null;
  async function submit(event: FormEvent) {
    event.preventDefault();
    setNotice("");
    setBusy(true);
    try {
      if (connection.data?.connected) {
        unwrap(
          await api.POST("/api/v1/me/google/disconnect", {
            body: { password },
          }),
        );
        setPassword("");
        setNotice("Konto Google zostało odłączone. Pozostałe sesje wygasły.");
        await client.invalidateQueries({ queryKey: ["google-connection"] });
        await client.invalidateQueries({ queryKey: ["me"] });
      } else {
        const result = unwrap(
          await api.POST("/api/v1/auth/google/start", {
            body: { mode: "link", password, return_to: "/profile" },
          }),
        );
        setPassword("");
        window.location.assign(result.url);
      }
    } catch (e) {
      setNotice(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card google-connection">
      <h2>Logowanie Google</h2>
      {connection.isPending ? (
        <p role="status">Sprawdzamy połączenie…</p>
      ) : connection.isError ? (
        <>
          <p role="alert">Nie udało się sprawdzić połączenia Google.</p>
          <button className="button" onClick={() => void connection.refetch()}>
            Ponów
          </button>
        </>
      ) : external ? (
        <>
          <p className="form-note">
            Połączeniem konta Google zarządzasz pod głównym adresem Volleycrew.
            Zaloguj się tam hasłem.
          </p>
          <a
            className="button"
            href={`${config.data?.public_url}/profile`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Otwórz mój profil w nowej karcie
          </a>
        </>
      ) : me && !me.has_password ? (
        <p className="form-note">
          Google jest Twoją jedyną metodą logowania. Aby je odłączyć, najpierw
          ustaw login i hasło w swoim profilu.
        </p>
      ) : (
        <>
          <p>
            {connection.data?.connected
              ? "Konto Google jest połączone. Nadal możesz logować się hasłem."
              : "Połącz Google ze swoim istniejącym profilem. Przy kolejnych wejściach wystarczy przycisk Google."}
          </p>
          <form onSubmit={(event) => void submit(event)}>
            <PasswordField
              label="Hasło potwierdzające zmianę"
              value={password}
              onChange={setPassword}
              disabled={busy}
            />
            <button className="button" disabled={busy}>
              {connection.data?.connected
                ? "Odłącz konto Google"
                : "Połącz konto Google"}
            </button>
          </form>
        </>
      )}
      {notice && (
        <p className="form-notice" role="status">
          {notice}
        </p>
      )}
    </section>
  );
}

export function GoogleJoin({ token }: { token: string }) {
  const config = useGoogleConfig();
  const external = usePublicGoogle(config.data?.public_url);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  if (!config.data?.enabled || !token) return null;
  async function start() {
    setBusy(true);
    setError("");
    try {
      const result = unwrap(
        await api.POST("/api/v1/auth/google/start", {
          body: { mode: "register", invite_token: token, return_to: "/" },
        }),
      );
      window.location.assign(result.url);
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  }
  return (
    <div className="google-access">
      {external ? (
        <a
          className="google-button"
          href={`${config.data.public_url}/join#${encodeURIComponent(token)}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          <GoogleLabel join />
        </a>
      ) : (
        <button
          type="button"
          className="google-button"
          disabled={busy}
          onClick={() => void start()}
        >
          {busy ? "Łączymy z Google…" : <GoogleLabel join />}
        </button>
      )}
      <p className="form-note">
        Po wyborze Google sprawdzisz i poprawisz imię oraz nazwisko. Login i
        hasło nie będą wymagane.
        {external &&
          " Dołączenie otworzy główny adres Volleycrew w nowej karcie."}
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <p className="form-note">
        Możesz też dołączyć poniżej, wybierając login i hasło.
      </p>
    </div>
  );
}

export function GooglePasswordStart() {
  const config = useGoogleConfig();
  const external = usePublicGoogle(config.data?.public_url);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function start() {
    setBusy(true);
    setError("");
    try {
      const result = unwrap(
        await api.POST("/api/v1/auth/google/start", {
          body: { mode: "password", return_to: "/profile" },
        }),
      );
      window.location.assign(result.url);
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  }
  return (
    <>
      <p className="form-note">
        Logujesz się przez Google. Możesz dodać login i hasło jako drugi sposób
        dostępu. Najpierw potwierdzisz to samo konto Google.
      </p>
      {!config.data?.enabled ? (
        <p className="form-note">
          Google jest teraz niedostępne. Organizator może przekazać Ci link do
          ustawienia loginu i hasła.
        </p>
      ) : external ? (
        <a
          className="button"
          href={`${config.data.public_url}/profile`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Otwórz profil pod głównym adresem
        </a>
      ) : (
        <button
          className="button primary"
          disabled={busy}
          onClick={() => void start()}
        >
          Ustaw login i hasło
        </button>
      )}
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
    </>
  );
}
