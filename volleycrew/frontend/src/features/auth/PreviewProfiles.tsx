import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, message, unwrap } from "../../lib/api/client";
import { useSession } from "./useSession";

export function PreviewProfiles() {
  const client = useQueryClient();
  const session = useSession();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!import.meta.env.DEV || import.meta.env.VITE_LOCAL_PREVIEW !== "true")
    return null;
  async function switchProfile(id: string) {
    setBusy(true);
    setError("");
    try {
      if (session.data) unwrap(await api.POST("/api/v1/auth/logout"));
      await client.cancelQueries();
      client.clear();
      const user = unwrap(
        await api.POST("/api/v1/auth/login", {
          body: { profile_id: id, pin: "123456" },
        }),
      );
      client.setQueryData(["me"], user);
      navigate("/calendar", { replace: true });
    } catch (e) {
      setError(message(e));
      await client.invalidateQueries({ queryKey: ["me"] });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="preview-profiles"
      aria-label="Profile podglądu lokalnego"
    >
      <span>Podgląd lokalny</span>
      <div className="row-actions">
        {[
          ["d80b3a15-f958-4b52-9d96-9e5fe2200001", "Admin"],
          ["d80b3a15-f958-4b52-9d96-9e5fe2200002", "User"],
        ].map(([id, name]) => (
          <button
            key={id}
            className={`button small ${session.data?.id === id ? "primary" : ""}`}
            disabled={busy || session.data?.id === id}
            onClick={() => void switchProfile(id)}
          >
            Wejdź jako {name}
          </button>
        ))}
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
