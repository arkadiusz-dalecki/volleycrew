import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { rememberProfile } from "./rememberedProfile";
import { useSession } from "./useSession";

const ViewModeContext = createContext({
  playerView: false,
  setPlayerView: (_value: boolean) => {
    void _value;
  },
});

export function ViewModeProvider({ children }: { children: ReactNode }) {
  const { data: me } = useSession();
  const storageKey = `volleycrew:view:${me?.id ?? "anonymous"}`;
  const [playerView, setPlayerView] = useState(() => {
    try {
      return sessionStorage.getItem(storageKey) === "player";
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey, playerView ? "player" : "admin");
    } catch {
      /* The switch also works with storage disabled. */
    }
  }, [storageKey, playerView]);
  useEffect(() => {
    if (me) rememberProfile(me.id);
  }, [me]);
  return (
    <ViewModeContext.Provider value={{ playerView, setPlayerView }}>
      {children}
    </ViewModeContext.Provider>
  );
}

// This module keeps the view context and its consumer together.
// eslint-disable-next-line react-refresh/only-export-components
export function useAdminView() {
  const session = useSession();
  const { playerView } = useContext(ViewModeContext);
  return session.data?.role === "admin" && !playerView;
}

export function ViewModeSwitch() {
  const navigate = useNavigate();
  const location = useLocation();
  const session = useSession();
  const { playerView, setPlayerView } = useContext(ViewModeContext);
  if (session.data?.role !== "admin") return null;
  return (
    <div className="view-mode-bar" role="group" aria-label="Widok aplikacji">
      <span>Widok</span>
      <button
        className="button small"
        aria-pressed={!playerView}
        onClick={() => setPlayerView(false)}
      >
        Administrator
      </button>
      <button
        className="button small"
        aria-pressed={playerView}
        onClick={() => {
          setPlayerView(true);
          if (location.pathname.startsWith("/admin/")) void navigate("/");
        }}
      >
        Użytkownik
      </button>
      {playerView && <small>Podgląd na Twoim koncie</small>}
    </div>
  );
}
