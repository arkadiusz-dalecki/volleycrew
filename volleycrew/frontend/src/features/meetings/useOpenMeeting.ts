import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api, message, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";

type Meeting = components["schemas"]["MeetingSummary"];
export function useOpenMeeting() {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const client = useQueryClient();
  async function open(item: Meeting) {
    if (busy) return;
    if (item.persisted) {
      navigate(`/meetings/${item.id}`);
      return;
    }
    setBusy(item.id);
    setError("");
    try {
      const result = unwrap(
        await api.POST("/api/v1/meetings/resolve", {
          body: {
            schedule_version_id: item.schedule_version_id,
            source_date: item.source_date,
          },
        }),
      );
      client.setQueryData(["meeting", result.id], result);
      await client.invalidateQueries({ queryKey: ["calendar"] });
      await client.invalidateQueries({ queryKey: ["next-meeting"] });
      navigate(`/meetings/${result.id}`);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(null);
    }
  }
  return { open, busy, error };
}
