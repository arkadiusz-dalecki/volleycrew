import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

it("recovers from a 503 response when the user retries", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({ code: "not_ready", message: "Not ready" }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "ready" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  const { ServiceStatus } = await import("./ServiceStatus");
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ServiceStatus />
    </QueryClientProvider>,
  );
  expect(
    await screen.findByText("Usługa chwilowo niedostępna"),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Ponów połączenie" }));
  expect(
    await screen.findByText("Połączenie z usługą działa"),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(2);
  client.clear();
});
