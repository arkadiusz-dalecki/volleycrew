import { useRef, useState, type ReactNode, type TouchEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { api, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { useOpenMeeting } from "./useOpenMeeting";

type Meeting = components["schemas"]["MeetingSummary"];
type Direction = "previous" | "next";
const controls =
  "a, button, input, select, textarea, label, form, dialog, [role='button'], [contenteditable='true']";

export function MeetingNavigation({
  meeting,
  children,
}: {
  meeting: Meeting;
  children: ReactNode;
}) {
  const opener = useOpenMeeting();
  const [opening, setOpening] = useState(false);
  const navigating = useRef(false);
  const gesture = useRef<{ x: number; y: number; at: number } | null>(null);
  const adjacent = useQuery({
    queryKey: ["calendar", "adjacent", meeting.id, meeting.starts_at],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/meetings/adjacent", {
          params: {
            query: { starts_at: meeting.starts_at, meeting_id: meeting.id },
          },
          signal,
        }),
      ),
    refetchInterval: 30_000,
  });

  async function move(direction: Direction) {
    const target = adjacent.data?.[direction];
    if (!target || navigating.current || adjacent.isError) return;
    navigating.current = true;
    setOpening(true);
    try {
      await opener.open(target);
    } finally {
      navigating.current = false;
      setOpening(false);
    }
  }

  function start(event: TouchEvent<HTMLDivElement>) {
    gesture.current = null;
    if (
      event.touches.length !== 1 ||
      (event.target instanceof Element && event.target.closest(controls)) ||
      document.querySelector("dialog[open]")
    )
      return;
    const touch = event.touches[0];
    gesture.current = { x: touch.clientX, y: touch.clientY, at: Date.now() };
  }

  function track(event: TouchEvent<HTMLDivElement>) {
    const origin = gesture.current;
    if (!origin) return;
    const touch = event.touches[0];
    if (
      event.touches.length !== 1 ||
      (Math.abs(touch.clientY - origin.y) > 12 &&
        Math.abs(touch.clientY - origin.y) > Math.abs(touch.clientX - origin.x))
    )
      gesture.current = null;
  }

  function finish(event: TouchEvent<HTMLDivElement>) {
    const origin = gesture.current;
    gesture.current = null;
    if (!origin || event.touches.length || event.changedTouches.length !== 1)
      return;
    const touch = event.changedTouches[0];
    const dx = touch.clientX - origin.x;
    const dy = touch.clientY - origin.y;
    if (
      Math.abs(dx) >= 60 &&
      Math.abs(dx) > Math.abs(dy) * 1.5 &&
      Date.now() - origin.at < 1000
    )
      void move(dx < 0 ? "next" : "previous");
  }

  return (
    <div
      className="meeting-navigation-surface"
      onTouchStart={start}
      onTouchMove={track}
      onTouchEnd={finish}
      onTouchCancel={() => (gesture.current = null)}
    >
      <nav
        className="meeting-navigation"
        aria-label="Nawigacja między spotkaniami"
      >
        <button
          className="button"
          disabled={opening || adjacent.isError || !adjacent.data?.previous}
          onClick={() => void move("previous")}
          aria-label="Poprzednie spotkanie"
        >
          <ChevronLeft size={20} /> Poprzednie
        </button>
        <button
          className="button"
          disabled={opening || adjacent.isError || !adjacent.data?.next}
          onClick={() => void move("next")}
          aria-label="Następne spotkanie"
        >
          Następne <ChevronRight size={20} />
        </button>
      </nav>
      <p className="form-note meeting-swipe-hint" role="status">
        {opening
          ? "Otwieramy spotkanie…"
          : adjacent.isPending
            ? "Wczytujemy sąsiednie spotkania…"
            : "Przesuń w lewo lub w prawo, aby zmienić spotkanie."}
      </p>
      {adjacent.isError && (
        <p role="alert" className="form-error">
          Nie udało się wczytać sąsiednich spotkań.{" "}
          <button
            className="button small"
            onClick={() => void adjacent.refetch()}
          >
            Ponów nawigację
          </button>
        </p>
      )}
      {opener.error && (
        <p role="alert" className="form-error">
          {opener.error}
        </p>
      )}
      {children}
    </div>
  );
}
