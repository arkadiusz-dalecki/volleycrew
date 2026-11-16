import { Component, Suspense, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { LoadingCard } from "./LoadingCard";

class RouteError extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? (
      <section className="card" role="alert">
        <h1>Nie udało się otworzyć widoku</h1>
        <p className="form-note">
          Sprawdź połączenie i wczytaj stronę ponownie.
        </p>
        <button className="button" onClick={() => window.location.reload()}>
          Wczytaj ponownie
        </button>
      </section>
    ) : (
      this.props.children
    );
  }
}

export function RouteContent({ children }: { children: ReactNode }) {
  const location = useLocation();
  return (
    <div className="route-content">
      <RouteError key={location.pathname}>
        <Suspense fallback={<LoadingCard message="Wczytujemy widok…" />}>
          {children}
        </Suspense>
      </RouteError>
    </div>
  );
}
