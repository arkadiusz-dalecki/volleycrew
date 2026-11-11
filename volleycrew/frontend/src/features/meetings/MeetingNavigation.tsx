import {
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
  type TouchEvent,
} from "react";
import { useLocation } from "react-router-dom";
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
  const location = useLocation();
  const surface = useRef<HTMLDivElement>(null);
  const card = () =>
    surface.current?.querySelector<HTMLElement>(".meeting-card");
  const reducedMotion = () =>
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useLayoutEffect(() => {
    const direction = location.state?.meetingDirection;
    const element =
      surface.current?.querySelector<HTMLElement>(".meeting-card");
    if (
      !element ||
      !direction ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return;
    const offset = direction === "next" ? 64 : -64;
    const animation = element.animate(
      [
        { transform: `translateX(${offset}px)`, opacity: 0 },
        { transform: "translateX(0)", opacity: 1 },
      ],
      { duration: 300, easing: "cubic-bezier(0.22, 1, 0.36, 1)" },
    );
    return () => animation.cancel();
  }, [location.key, location.state]);

  function resetDrag() {
    gesture.current = null;
    surface.current?.removeAttribute("data-dragging");
    surface.current?.style.setProperty("--meeting-drag", "0px");
  }
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
      await opener.open(target, {
        direction,
        beforeNavigate: async () => {
          const element = card();
          if (!element || reducedMotion()) return;
          const animation = element.animate(
            [
              { transform: getComputedStyle(element).transform, opacity: 1 },
              {
                transform: `translateX(${direction === "next" ? -100 : 100}%)`,
                opacity: 0,
              },
            ],
            {
              duration: 220,
              easing: "cubic-bezier(0.4, 0, 1, 1)",
              fill: "forwards",
            },
          );
          await animation.finished;
        },
      });
    } finally {
      navigating.current = false;
      setOpening(false);
      resetDrag();
    }
  }

  function start(event: TouchEvent<HTMLDivElement>) {
    resetDrag();
    if (
      navigating.current ||
      !(
        event.target instanceof Element && event.target.closest(".meeting-card")
      ) ||
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
    ) {
      resetDrag();
      return;
    }
    const dx = touch.clientX - origin.x;
    if (
      Math.abs(dx) < 12 ||
      Math.abs(dx) <= Math.abs(touch.clientY - origin.y) * 1.5
    )
      return;
    const available =
      !adjacent.isError && adjacent.data?.[dx < 0 ? "next" : "previous"];
    surface.current?.setAttribute("data-dragging", "true");
    surface.current?.style.setProperty(
      "--meeting-drag",
      `${reducedMotion() ? 0 : dx * (available ? 0.85 : 0.15)}px`,
    );
  }

  function finish(event: TouchEvent<HTMLDivElement>) {
    const origin = gesture.current;
    gesture.current = null;
    if (!origin || event.touches.length || event.changedTouches.length !== 1) {
      resetDrag();
      return;
    }
    const touch = event.changedTouches[0];
    const dx = touch.clientX - origin.x;
    const dy = touch.clientY - origin.y;
    if (
      Math.abs(dx) >= 60 &&
      Math.abs(dx) > Math.abs(dy) * 1.5 &&
      Date.now() - origin.at < 1000
    ) {
      const direction = dx < 0 ? "next" : "previous";
      if (!adjacent.isError && adjacent.data?.[direction]) {
        void move(direction);
        return;
      }
    }
    resetDrag();
  }

  return (
    <div
      ref={surface}
      className="meeting-navigation-surface"
      data-meeting-id={meeting.id}
      onTouchStart={start}
      onTouchMove={track}
      onTouchEnd={finish}
      onTouchCancel={resetDrag}
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
