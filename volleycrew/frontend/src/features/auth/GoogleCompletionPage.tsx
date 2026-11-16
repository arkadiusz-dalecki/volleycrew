import { useId, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, message, unwrap } from "../../lib/api/client";
import { AuthCard, Pending } from "./AuthPages";
import { useAuthLinkToken } from "./useAuthLinkToken";
import { PasswordField, UsernameField } from "./CredentialFields";
import { rememberUsername } from "./rememberedUsername";

export function GoogleCompletionPage({
  passwordSetup = false,
}: {
  passwordSetup?: boolean;
}) {
  const token = useAuthLinkToken();
  return (
    <AuthCard
      title={passwordSetup ? "Ustaw login i hasło" : "Sprawdź dane i dołącz"}
      subtitle={
        passwordSetup
          ? "Konto Google zostało potwierdzone. Dodaj drugi sposób logowania."
          : "Dane podpowiedziało Google. Popraw je, jeśli trzeba — używamy ich na szkolnej liście podpisów."
      }
    >
      <CompletionProof
        key={token}
        token={token}
        passwordSetup={passwordSetup}
      />
      <Link className="text-link" to={passwordSetup ? "/profile" : "/login"}>
        {passwordSetup ? "Wróć do profilu" : "Mam już profil — zaloguj się"}
      </Link>
    </AuthCard>
  );
}

function CompletionProof({
  token,
  passwordSetup,
}: {
  token: string;
  passwordSetup: boolean;
}) {
  const instance = useId();
  // Tokens stay in this mounted form; they must never become query cache keys.
  const proof = useQuery({
    queryKey: ["google-completion", instance],
    enabled: Boolean(token),
    staleTime: 0,
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
    queryFn: async () =>
      unwrap(
        await api.POST("/api/v1/auth/google/completion", { body: { token } }),
      ),
  });
  return (
    <>
      {!token ? (
        <p role="alert" className="form-error">
          {passwordSetup
            ? "Otwórz swój profil i ponownie potwierdź konto Google."
            : "Otwórz ponownie link zaproszenia i wybierz Dołącz przez Google."}
        </p>
      ) : proof.isPending ? (
        <p role="status">Sprawdzamy potwierdzenie Google…</p>
      ) : proof.isError ? (
        <>
          <p role="alert" className="form-error">
            {message(proof.error)}{" "}
            {passwordSetup
              ? "Rozpocznij ponownie w swoim profilu."
              : "Otwórz ponownie zaproszenie, aby zacząć od nowa."}
          </p>
          <button className="button" onClick={() => void proof.refetch()}>
            Spróbuj ponownie
          </button>
        </>
      ) : proof.data?.purpose !== (passwordSetup ? "password" : "register") ? (
        <p role="alert">Nieprawidłowe potwierdzenie. Rozpocznij ponownie.</p>
      ) : (
        <CompletionForm
          token={token}
          passwordSetup={passwordSetup}
          first={proof.data.first_name}
          last={proof.data.last_name}
        />
      )}
    </>
  );
}

function CompletionForm({
  token,
  passwordSetup,
  first,
  last,
}: {
  token: string;
  passwordSetup: boolean;
  first: string;
  last: string;
}) {
  const [firstName, setFirstName] = useState(first),
    [lastName, setLastName] = useState(last);
  const [nickname, setNickname] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState(""),
    [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const client = useQueryClient(),
    navigate = useNavigate();
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (passwordSetup && password !== repeat) {
      setError("Podane hasła muszą być takie same.");
      return;
    }
    setBusy(true);
    try {
      const result = passwordSetup
        ? await api.POST("/api/v1/me/google/password", {
            body: { token, username, password },
          })
        : await api.POST("/api/v1/auth/google/register", {
            body: {
              token,
              first_name: firstName,
              last_name: lastName,
              nickname: nickname || null,
            },
          });
      const user = unwrap(result);
      await client.cancelQueries();
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "me",
      });
      client.setQueryData(["me"], user);
      rememberUsername(user.username ?? "");
      setPassword("");
      setRepeat("");
      navigate(passwordSetup ? "/profile" : "/", { replace: true });
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={(e) => void submit(e)}>
      {passwordSetup ? (
        <>
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
            match={password}
            onChange={setRepeat}
            fresh
            disabled={busy}
          />
        </>
      ) : (
        <>
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
              maxLength={40}
              autoComplete="nickname"
              disabled={busy}
            />
          </label>
          <p className="form-note">
            Dołączysz z kontem Google. Login i hasło możesz dodać później w
            swoim profilu.
          </p>
        </>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <Pending busy={busy}>
        {passwordSetup ? "Zapisz login i hasło" : "Dołączam do gry"}
      </Pending>
    </form>
  );
}
