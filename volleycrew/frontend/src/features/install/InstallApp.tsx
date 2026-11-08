import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Download, Share } from "lucide-react";
import { ConfirmDialog } from "../../components/ConfirmDialog";

type InstallPrompt = Event & {
  prompt: () => Promise<{ outcome: "accepted" | "dismissed" }>;
};
const InstallContext = createContext<{
  prompt: InstallPrompt | null;
  installed: boolean;
  clearPrompt: () => void;
}>({ prompt: null, installed: false, clearPrompt: () => {} });

export function InstallProvider({ children }: { children: ReactNode }) {
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [installed, setInstalled] = useState(false);
  useEffect(() => {
    const display = window.matchMedia("(display-mode: standalone)");
    const update = () =>
      setInstalled(
        display.matches ||
          !!(navigator as Navigator & { standalone?: boolean }).standalone,
      );
    const ready = (event: Event) => {
      event.preventDefault();
      setPrompt(event as InstallPrompt);
    };
    const done = () => {
      setInstalled(true);
      setPrompt(null);
    };
    update();
    window.addEventListener("beforeinstallprompt", ready);
    window.addEventListener("appinstalled", done);
    display.addEventListener("change", update);
    return () => {
      window.removeEventListener("beforeinstallprompt", ready);
      window.removeEventListener("appinstalled", done);
      display.removeEventListener("change", update);
    };
  }, []);
  return (
    <InstallContext.Provider
      value={{ prompt, installed, clearPrompt: () => setPrompt(null) }}
    >
      {children}
    </InstallContext.Provider>
  );
}

export function InstallApp() {
  const { prompt, installed, clearPrompt } = useContext(InstallContext);
  const [help, setHelp] = useState(false);
  const [busy, setBusy] = useState(false);
  const ios =
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const android = /Android/.test(navigator.userAgent);
  if (installed) return null;
  async function install() {
    if (!prompt) {
      setHelp(true);
      return;
    }
    setBusy(true);
    try {
      await prompt.prompt();
    } catch {
      setHelp(true);
    } finally {
      clearPrompt();
      setBusy(false);
    }
  }
  return (
    <div className="install-app">
      <button
        className="button"
        disabled={busy}
        onClick={(event) => {
          // Safari does not focus a button on a pointer click; retain a return target.
          event.currentTarget.focus();
          void install();
        }}
      >
        <Download size={18} /> Dodaj aplikację do telefonu
      </button>
      {help && (
        <ConfirmDialog
          title="Dodaj Volleycrew do ekranu głównego"
          onDismiss={() => setHelp(false)}
        >
          {ios ? (
            <>
              <p>Otwórz Volleycrew w Safari.</p>
              <ol>
                <li>
                  Dotknij „Udostępnij”{" "}
                  <Share size={16} aria-label="kwadrat ze strzałką w górę" /> w
                  menu przeglądarki.
                </li>
                <li>Wybierz „Do ekranu początkowego”.</li>
                <li>
                  Jeśli widzisz „Otwórz jako aplikację”, pozostaw tę opcję
                  włączoną, a następnie dotknij „Dodaj”.
                </li>
              </ol>
              <p>Ikona Volleycrew pojawi się obok pozostałych aplikacji.</p>
            </>
          ) : android ? (
            <>
              <p>
                W Chrome otwórz menu ⋮ i wybierz „Zainstaluj aplikację” lub
                „Dodaj do ekranu głównego”, a następnie potwierdź.
              </p>
              <p>
                Jeśli otwarto stronę wewnątrz innej aplikacji, otwórz ją
                najpierw w Chrome.
              </p>
            </>
          ) : (
            <p>
              Na telefonie otwórz Volleycrew w Safari lub Chrome. Na komputerze
              poszukaj opcji „Zainstaluj” w pasku adresu lub menu przeglądarki.
            </p>
          )}
          {!window.isSecureContext && (
            <p>Instalacja aplikacji wymaga otwarcia strony przez HTTPS.</p>
          )}
          <div className="row-actions">
            <button className="button primary" onClick={() => setHelp(false)}>
              Rozumiem
            </button>
          </div>
        </ConfirmDialog>
      )}
    </div>
  );
}
