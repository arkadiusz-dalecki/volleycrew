import { lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { InstallProvider } from "../features/install/InstallApp";
import { ViewModeProvider } from "../features/auth/ViewMode";
import {
  LoginPage,
  RegisterPage,
  ResetPasswordPage,
  Protected,
} from "../features/auth/AuthPages";
import { useSession } from "../features/auth/useSession";
import { RouteContent } from "../components/RouteContent";

const PrivateApp = lazy(() =>
  import("./PrivateApp").then((module) => ({ default: module.PrivateApp })),
);
const GoogleCompletionPage = lazy(() =>
  import("../features/auth/GoogleCompletionPage").then((module) => ({
    default: module.GoogleCompletionPage,
  })),
);

export function App() {
  const session = useSession();
  return (
    <InstallProvider>
      <ViewModeProvider key={session.data?.id ?? "anonymous"}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          {import.meta.env.DEV && (
            <Route path="/preview/login" element={<LoginPage preview />} />
          )}
          <Route
            path="/join/google"
            element={
              <RouteContent>
                <GoogleCompletionPage />
              </RouteContent>
            }
          />
          <Route
            path="/profile/password"
            element={
              <Protected>
                <RouteContent>
                  <GoogleCompletionPage passwordSetup />
                </RouteContent>
              </Protected>
            }
          />
          <Route path="/join" element={<RegisterPage key="join" />} />
          <Route
            path="/join/:token"
            element={<Navigate to="/join" replace />}
          />
          <Route
            path="/setup"
            element={<RegisterPage bootstrap key="setup" />}
          />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route
            path="/reset-password/:token"
            element={<Navigate to="/reset-password" replace />}
          />
          <Route
            path="*"
            element={
              <Protected>
                <RouteContent>
                  <PrivateApp />
                </RouteContent>
              </Protected>
            }
          />
        </Routes>
      </ViewModeProvider>
    </InstallProvider>
  );
}
