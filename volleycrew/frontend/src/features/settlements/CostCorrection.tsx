import { useState, type FormEvent } from "react";
import { api, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { useRoomAction } from "../room/useRoomAction";
import { CostField } from "./CostField";
import { amountText, money, toGrosz } from "./money";

type Attendance = components["schemas"]["AttendanceView"];

export function CostCorrection({ attendance }: { attendance: Attendance }) {
  const [cost, setCost] = useState(amountText(attendance.cost_grosz ?? 0));
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<
    components["schemas"]["CostPreview"] | null
  >(null);
  const action = useRoomAction();
  const params = { path: { meeting_id: attendance.meeting_id } };
  function show(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim()) return;
    void action.run(async () => {
      setPreview(
        unwrap(
          await api.POST("/api/v1/admin/meetings/{meeting_id}/cost/preview", {
            params,
            body: {
              expected_version: attendance.version,
              cost_grosz: toGrosz(cost),
              reason,
            },
          }),
        ),
      );
    });
  }
  function commit() {
    if (!preview) return;
    void action.run(
      async (key) =>
        unwrap(
          await api.PUT("/api/v1/admin/meetings/{meeting_id}/cost", {
            params: { ...params, header: { "Idempotency-Key": key } },
            body: {
              expected_version: preview.version,
              cost_grosz: preview.cost_grosz,
              reason,
            },
          }),
        ),
      () => {
        setPreview(null);
        setReason("");
      },
    );
  }
  return (
    <details className="confirmation-panel">
      <summary>Korekta kosztu spotkania</summary>
      <form method="post" onSubmit={show}>
        <CostField
          value={cost}
          onChange={(value) => {
            setCost(value);
            setPreview(null);
          }}
          disabled={action.busy}
        />
        <label className="form-field">
          Powód korekty kosztu
          <textarea
            name="reason"
            required
            maxLength={500}
            value={reason}
            disabled={action.busy}
            onChange={(event) => {
              setReason(event.target.value);
              setPreview(null);
            }}
          />
        </label>
        <button className="button" disabled={action.busy || action.canRetry}>
          Pokaż podgląd korekty kosztu
        </button>
      </form>
      {preview && (
        <>
          <p>Nowy koszt {money(preview.cost_grosz)}</p>
          <ul>
            {preview.shares
              .filter((share) => share.delta)
              .map((share) => {
                const person = attendance.players.find(
                  (row) => row.player.id === share.player_id,
                )?.player;
                return (
                  <li key={share.player_id}>
                    {person
                      ? person.first_name + " " + person.last_name
                      : "Uczestnik"}{" "}
                    · {money(share.amount)} ({share.delta > 0 ? "+" : ""}
                    {money(share.delta)})
                  </li>
                );
              })}
          </ul>
          <button
            type="button"
            className="button primary"
            disabled={
              action.busy ||
              action.canRetry ||
              preview.version !== attendance.version
            }
            onClick={commit}
          >
            Zatwierdź korektę kosztu
          </button>
        </>
      )}
      {action.error && <p role="alert">{action.error}</p>}
      {action.canRetry && (
        <button
          type="button"
          className="button"
          disabled={action.busy}
          onClick={() => void action.retry()}
        >
          Ponów zapis
        </button>
      )}
    </details>
  );
}
