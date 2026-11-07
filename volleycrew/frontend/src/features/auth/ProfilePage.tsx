import { HistoryPanel } from "../room/HistoryPanel";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { LockKeyhole, UserRound } from "lucide-react";
import { api, message, unwrap } from "../../lib/api/client";
import { useSession } from "./useSession";

import { priorityLabel } from "./labels";

export function ProfilePage() {
  const { data: me } = useSession();
  const [firstName, setFirstName] = useState(me?.first_name ?? "");
  const [lastName, setLastName] = useState(me?.last_name ?? "");
  const [nickname, setNickname] = useState(me?.nickname ?? "");
  const [currentPin, setCurrentPin] = useState("");
  const [pin, setPin] = useState("");
  const [repeat, setRepeat] = useState("");
  const [notice, setNotice] = useState("");
  const [pinNotice, setPinNotice] = useState("");
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
    setPinNotice("");
    if (pin !== repeat) {
      setPinNotice("Podane PIN-y muszą być takie same.");
      return;
    }
    setBusy(true);
    try {
      unwrap(
        await api.POST("/api/v1/me/pin", {
          body: { current_pin: currentPin, pin },
        }),
      );
      setCurrentPin("");
      setPin("");
      setRepeat("");
      setPinNotice("PIN zmieniony. Pozostałe urządzenia zostały wylogowane.");
    } catch (e) {
      setPinNotice(message(e));
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
      {me.role === "admin" && (
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
            <h2>Zmiana PIN-u</h2>
            <LockKeyhole size={20} />
          </div>
          <form onSubmit={(e) => void change(e)}>
            <label className="form-field">
              Obecny PIN
              <input
                type="password"
                inputMode="numeric"
                autoComplete="current-password"
                value={currentPin}
                onChange={(e) => setCurrentPin(e.target.value)}
                pattern="[0-9]{6}"
                maxLength={6}
                minLength={6}
                required
              />
            </label>
            <label className="form-field">
              Nowy PIN
              <input
                type="password"
                inputMode="numeric"
                autoComplete="new-password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                pattern="[0-9]{6}"
                maxLength={6}
                minLength={6}
                required
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
                maxLength={6}
                minLength={6}
                required
              />
            </label>
            <button className="button primary" disabled={busy}>
              Zmień PIN
            </button>
            <p className="form-notice" role="status">
              {pinNotice}
            </p>
          </form>
        </section>
      </div>
      <HistoryPanel />
    </>
  );
}
