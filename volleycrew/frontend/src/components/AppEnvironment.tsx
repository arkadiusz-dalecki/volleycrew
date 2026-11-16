import { useEffect, useRef, useSyncExternalStore } from "react";
import { useLocation, useNavigationType } from "react-router-dom";
import { useSession } from "../features/auth/useSession";

function subscribeOnline(callback: () => void) {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}

export function ConnectionNotice() {
  const online = useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
  const session = useSession();
  return !online ? (
    <p role="status" className="connection-notice">
      Brak połączenia. Pola formularzy pozostają na ekranie. Po odzyskaniu sieci
      ponów zapis ręcznie.
    </p>
  ) : session.isError ? (
    <p role="status" className="connection-notice">
      Nie udało się odświeżyć sesji. Sprawdź połączenie; pokazujemy ostatnio
      pobrane dane.
      <button className="button" onClick={() => void session.refetch()}>
        Sprawdź połączenie
      </button>
    </p>
  ) : null;
}

export function AppEnvironment() {
  const location = useLocation();
  const navigationType = useNavigationType();
  const previousPath = useRef<string | null>(null);
  useEffect(() => {
    const isMeeting = (path: string | null) =>
      path === "/" || /^\/meetings\/[^/]+$/.test(path ?? "");
    const adjacentNavigation =
      navigationType === "PUSH" &&
      isMeeting(previousPath.current) &&
      isMeeting(location.pathname) &&
      ["previous", "next"].includes(location.state?.meetingDirection);
    previousPath.current = location.pathname;
    if (!adjacentNavigation) {
      document.getElementById("main")?.focus({ preventScroll: true });
      window.scrollTo(0, 0);
    }
    document.title = `Volleycrew · ${location.pathname.startsWith("/ranking") ? "Ranking" : location.pathname === "/calendar" ? "Kalendarz" : location.pathname === "/profile" ? "Mój profil" : location.pathname.startsWith("/admin") ? "Organizator" : "Spotkanie"}`;
  }, [location.pathname, location.state, navigationType]);
  useEffect(() => {
    const viewport = window.visualViewport;
    let frame = 0;
    function update() {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const editable = document.activeElement?.matches(
          'input:not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"]),textarea,[contenteditable="true"]',
        );
        const keyboard = !!(
          viewport &&
          editable &&
          viewport.scale === 1 &&
          window.innerHeight - viewport.height > 150
        );
        document.documentElement.dataset.keyboardOpen = String(keyboard);
        document.documentElement.style.setProperty(
          "--visible-height",
          `${viewport?.height ?? window.innerHeight}px`,
        );
      });
    }
    viewport?.addEventListener("resize", update);
    viewport?.addEventListener("scroll", update);
    document.addEventListener("focusin", update);
    document.addEventListener("focusout", update);
    update();
    return () => {
      cancelAnimationFrame(frame);
      viewport?.removeEventListener("resize", update);
      viewport?.removeEventListener("scroll", update);
      document.removeEventListener("focusin", update);
      document.removeEventListener("focusout", update);
      delete document.documentElement.dataset.keyboardOpen;
      document.documentElement.style.removeProperty("--visible-height");
    };
  }, []);
  return null;
}
