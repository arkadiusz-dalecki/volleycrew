import { useAdminView } from "./ViewMode";
import { HistoryPanel } from "../room/HistoryPanel";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { LockKeyhole, UserRound } from "lucide-react";
import { api, message, unwrap } from "../../lib/api/client";
import { useSession } from "./useSession";

import { GoogleConnection, GoogleNotice } from "./GoogleAuth";
import { PasswordField } from "./CredentialFields";
import { priorityLabel } from "./labels";

export function ProfilePage() {
  const adminView = useAdminView();
  const { data: me } = useSession();
  const [firstName, setFirstName] = useState(me?.first_name ?? "");
  const [lastName, setLastName] = useState(me?.last_name ?? "");
  const [nickname, setNickname] = useState(me?.nickname ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [notice, setNotice] = useState("");
  const [passwordNotice, setPasswordNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  if (!me) return null;
  async function save(event: FormEvent) {
    event.preventDefault();
    setNotice("");
    setBusy(true);
    try {
      const user = unwrap(
        await api.PATCH("/api/v1/me", {
          body: {
            first_name: firstName,
            last_name: lastName,
            nickname: nickname || null,
          },
        }),
      );
      client.setQueryData(["me"], user);
      setNotice("Dane zostały zapisane.");
    } catch (e) {
      setNotice(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function change(event: FormEvent) {
    event.preventDefault();
    setPasswordNotice("");
    if (password !== repeat) {
      setPasswordNotice("Podane hasła muszą być takie same.");
      return;
    }
    setBusy(true);
    try {
      unwrap(
        await api.POST("/api/v1/me/password", {
          body: { current_password: currentPassword, password },
        }),
      );
      setCurrentPassword("");
      setPassword("");
      setRepeat("");
      setPasswordNotice(
        "Hasło zmienione. Pozostałe urządzenia zostały wylogowane.",
      );
    } catch (e) {
      setPasswordNotice(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <h1>Mój profil</h1>
        <p>Twoje dane i ustawienia dostępu do ekipy.</p>
      </div>
      <GoogleNotice />
      {adminView && (
        <Link className="button profile-admin-link" to="/admin/settings">
          Ustawienia ekipy
        </Link>
      )}
      <div className="profile-layout">
        <section className="card">
          <div className="section-title">
            <h2>
              {me.first_name} {me.last_name}
            </h2>
            <UserRound size={20} />
          </div>
          <p className="form-note">
            Login: <strong>{me.username}</strong>
          </p>
          <p className="private-status">
            Twój status: {priorityLabel(me.priority_status)}
            <small>Widoczny tylko dla Ciebie i organizatora.</small>
          </p>
          <form onSubmit={(e) => void save(e)}>
            <div className="form-row">
              <label className="form-field">
                Imię
                <input
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  autoComplete="given-name"
                  maxLength={80}
                  required
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
              />
              <small>Nie zmienia imienia i nazwiska na liście podpisów.</small>
            </label>
            <button className="button primary" disabled={busy}>
              Zapisz dane
            </button>
            <p className="form-notice" role="status">
              {notice}
            </p>
          </form>
        </section>
        <section className="card">
          <div className="section-title">
            <h2>Zmiana hasła</h2>
            <LockKeyhole size={20} />
          </div>
          <form onSubmit={(e) => void change(e)}>
            <PasswordField
              label="Obecne hasło"
              value={currentPassword}
              onChange={setCurrentPassword}
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
            <button className="button primary" disabled={busy}>
              Zmień hasło
            </button>
            <p className="form-notice" role="status">
              {passwordNotice}
            </p>
          </form>
        </section>
      </div>
      <GoogleConnection />
      <HistoryPanel />
    </>
  );
}
