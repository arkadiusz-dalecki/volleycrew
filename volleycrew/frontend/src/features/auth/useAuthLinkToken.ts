import { useLayoutEffect, useState } from "react";
import { useLocation } from "react-router-dom";

// Keep the secret only in the mounted form. Reloading requires reopening the link.
export function useAuthLinkToken({ allowQuery = false } = {}) {
  const location = useLocation();
  const incoming =
    (allowQuery && new URLSearchParams(location.search).get("token")) ||
    location.hash.slice(1);
  const [token, setToken] = useState(incoming);
  // Opening another fragment on this route may not remount the form.
  if (incoming && incoming !== token) setToken(incoming);
  useLayoutEffect(() => {
    if (window.location.hash || window.location.search) {
      // Preserve the router's history entry and Ingress prefix without scheduling
      // navigation that could race with session changes after form submission.
      window.history.replaceState(
        window.history.state,
        "",
        window.location.pathname,
      );
    }
  }, [location.key]);
  return token;
}
