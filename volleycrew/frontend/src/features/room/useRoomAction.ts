import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiFailure, message } from "../../lib/api/client";
import { refreshSchedule } from "../schedule/refresh";

type Attempt = {
  request: (key: string) => Promise<unknown>;
  key: string;
  done?: () => void;
};
export function useRoomAction() {
  const client = useQueryClient();
  const pending = useRef<Attempt | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [canRetry, setCanRetry] = useState(false);
  async function execute(attempt: Attempt) {
    setBusy(true);
    setError("");
    try {
      await attempt.request(attempt.key);
      pending.current = null;
      setCanRetry(false);
      attempt.done?.();
      await refreshSchedule(client);
    } catch (e) {
      setError(message(e));
      if (e instanceof ApiFailure && e.status < 500) {
        pending.current = null;
        setCanRetry(false);
        await refreshSchedule(client);
      } else setCanRetry(true);
    } finally {
      setBusy(false);
    }
  }
  async function run(request: Attempt["request"], done?: Attempt["done"]) {
    if (pending.current) return;
    const attempt = { request, done, key: crypto.randomUUID() };
    pending.current = attempt;
    await execute(attempt);
  }
  return {
    run,
    busy,
    error,
    canRetry,
    retry: () =>
      pending.current ? execute(pending.current) : Promise.resolve(),
  };
}
