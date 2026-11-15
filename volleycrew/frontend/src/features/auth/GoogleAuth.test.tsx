import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "../../lib/api/client";
import { GoogleConnection, GoogleJoin, GoogleLogin } from "./GoogleAuth";

vi.mock("../../lib/base", () => ({
  basePath: "/api/hassio_ingress/test-prefix",
  csrfCookieName: "vc_csrf_ingress",
}));

afterEach(cleanup);

function show(element: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(<QueryClientProvider client={client}>{element}</QueryClientProvider>);
}

it("Ingress opens Google login at the canonical public origin in a new tab", async () => {
  vi.spyOn(api, "GET").mockResolvedValue({
    data: { enabled: true, public_url: "https://volleycrew.test" },
    response: new Response(),
  } as never);
  show(<GoogleLogin />);
  const link = await screen.findByRole("link", {
    name: "Zaloguj przez Google",
  });
  expect(link).toHaveAttribute("href", "https://volleycrew.test/login");
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
  expect(
    screen.queryByRole("button", { name: "Zaloguj przez Google" }),
  ).not.toBeInTheDocument();
});

it("Ingress manages linking at the canonical profile instead of transferring its session", async () => {
  vi.spyOn(api, "GET").mockImplementation(
    async (path) =>
      ({
        data:
          path === "/api/v1/auth/google/config"
            ? { enabled: true, public_url: "https://volleycrew.test" }
            : { connected: false },
        response: new Response(),
      }) as never,
  );
  show(<GoogleConnection />);
  expect(
    await screen.findByRole("link", {
      name: "Otwórz mój profil w nowej karcie",
    }),
  ).toHaveAttribute("href", "https://volleycrew.test/profile");
  expect(
    screen.queryByLabelText("Hasło potwierdzające zmianę"),
  ).not.toBeInTheDocument();
});

it("Ingress carries the invitation only in the canonical invitation query", async () => {
  vi.spyOn(api, "GET").mockResolvedValue({
    data: { enabled: true, public_url: "https://volleycrew.test" },
    response: new Response(),
  } as never);
  const token = "isolated-invitation-token";
  show(<GoogleJoin token={token} />);
  const link = await screen.findByRole("link", { name: "Dołącz przez Google" });
  const target = new URL(link.getAttribute("href")!);
  expect(target.origin).toBe("https://volleycrew.test");
  expect(target.pathname).toBe("/join");
  expect(target.hash).toBe("");
  expect(target.searchParams.get("token")).toBe(token);
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
});
