import createClient from "openapi-fetch";
import { basePath, csrfCookieName } from "../base";
import type { paths } from "./schema";

// Same origin in production; Vite proxies /api in development.
export const api = createClient<paths>({
  baseUrl: window.location.origin + basePath,
  credentials: "same-origin",
});

api.use({
  async onRequest({ request }) {
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
      let token = document.cookie
        .split("; ")
        .find((item) => item.startsWith(`${csrfCookieName}=`))
        ?.slice(csrfCookieName.length + 1);
      if (!token) {
        const result = await api.GET("/api/v1/auth/csrf");
        if (!result.data)
          throw new Error("Nie można zabezpieczyć połączenia. Odśwież stronę.");
        token = result.data.token;
      }
      request.headers.set("X-CSRF-Token", token);
    }
    return request;
  },
  async onResponse({ request, response }) {
    if (response.status === 401) {
      const body = await response
        .clone()
        .json()
        .catch(() => null);
      if (body?.code === "unauthenticated" && !request.signal.aborted)
        window.dispatchEvent(new Event("volleycrew:session-expired"));
    }
  },
});

export class ApiFailure extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function unwrap<T>(result: {
  data?: T;
  error?: unknown;
  response: Response;
}): T {
  if (result.error || result.data === undefined) {
    const error = result.error as
      { code?: string; message?: string } | undefined;
    throw new ApiFailure(
      error?.code ?? "request_failed",
      error?.message ?? "Nie udało się wykonać czynności.",
      result.response.status,
    );
  }
  return result.data;
}

export function message(error: unknown): string {
  if (error instanceof TypeError)
    return "Nie udało się połączyć z usługą. Sprawdź sieć i ponów zapis ręcznie.";
  return error instanceof Error
    ? error.message
    : "Nie udało się połączyć z usługą. Spróbuj ponownie.";
}
