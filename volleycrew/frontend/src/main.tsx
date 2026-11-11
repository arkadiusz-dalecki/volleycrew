import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import "@fontsource/dm-sans/latin-400.css";
import "@fontsource/dm-sans/latin-500.css";
import "@fontsource/dm-sans/latin-600.css";
import "@fontsource/manrope/latin-700.css";
import "@fontsource/dm-sans/latin-ext-400.css";
import "@fontsource/dm-sans/latin-ext-500.css";
import "@fontsource/dm-sans/latin-ext-600.css";
import "@fontsource/manrope/latin-ext-700.css";
import { basePath } from "./lib/base";
import { App } from "./app/App";
import "./app/styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 15_000 } },
});

window.addEventListener("volleycrew:session-expired", () => {
  const expiredSession = queryClient.getQueryData(["me"]);
  // Late private responses must not clear queries on the logged-out screen.
  if (!expiredSession) return;
  void queryClient.cancelQueries().then(() => {
    // Authentication may have completed while the old requests were cancelled.
    if (queryClient.getQueryData(["me"]) !== expiredSession) return;
    queryClient.setQueryData(["me"], null);
    queryClient.removeQueries({
      predicate: (query) => query.queryKey[0] !== "me",
    });
  });
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={basePath || "/"}>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
