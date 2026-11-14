import { describe, expect, it } from "vitest";
import { unwrap } from "./client";

describe("rate limit messages", () => {
  it("shows the server retry interval without exposing response details", () => {
    expect(() =>
      unwrap({
        error: { code: "rate_limited", message: "Za dużo prób." },
        response: new Response(null, {
          status: 429,
          headers: { "Retry-After": "900" },
        }),
      }),
    ).toThrow("Za dużo prób. Spróbuj ponownie za 900 s.");
  });

  it("keeps the API message when the retry interval is absent or invalid", () => {
    for (const value of ["", "invalid", "-1", "Infinity"]) {
      expect(() =>
        unwrap({
          error: { code: "rate_limited", message: "Spróbuj później." },
          response: new Response(null, {
            status: 429,
            headers: { "Retry-After": value },
          }),
        }),
      ).toThrow("Spróbuj później.");
    }
  });
});
