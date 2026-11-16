import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, useLocation } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { RouteContent } from "./RouteContent";

function Page() {
  const [count, setCount] = useState(0);
  const location = useLocation();
  if (location.pathname === "/broken") throw new Error("Test route failure");
  return <button onClick={() => setCount(count + 1)}>Count {count}</button>;
}

it("keeps mounted content on navigation and recovers a failed route", () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  render(
    <MemoryRouter>
      <Link to="/meetings/next">Next</Link>
      <Link to="/broken">Broken</Link>
      <Link to="/calendar">Calendar</Link>
      <RouteContent>
        <Page />
      </RouteContent>
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Count 0" }));
  fireEvent.click(screen.getByRole("link", { name: "Next" }));
  expect(screen.getByRole("button", { name: "Count 1" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("link", { name: "Broken" }));
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Nie udało się otworzyć widoku",
  );
  fireEvent.click(screen.getByRole("link", { name: "Calendar" }));
  expect(screen.getByRole("button", { name: "Count 0" })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
