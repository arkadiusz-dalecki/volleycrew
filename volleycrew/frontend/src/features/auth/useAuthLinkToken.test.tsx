import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen, act, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { BrowserRouter } from "react-router-dom";
import { useAuthLinkToken } from "./useAuthLinkToken";

function Form() {
  const token = useAuthLinkToken({ allowQuery: true });
  return <output data-testid="token">{token}</output>;
}

afterEach(cleanup);

it("keeps the invitation when tracking query parameters precede its fragment", () => {
  window.history.replaceState(
    null,
    "",
    "/join?fbclid=tracking#test-invitation",
  );
  render(
    <StrictMode>
      <BrowserRouter>
        <Form />
      </BrowserRouter>
    </StrictMode>,
  );
  expect(screen.getByTestId("token")).toHaveTextContent("test-invitation");
  expect(window.location.href).toBe("http://localhost:3000/join");
});

it("reads a fragment delivered after the embedded browser opens the page", async () => {
  window.history.replaceState(null, "", "/join?fbclid=tracking");
  render(
    <BrowserRouter>
      <Form />
    </BrowserRouter>,
  );
  await act(async () => {
    window.location.hash = "test-invitation";
  });
  await waitFor(() =>
    expect(screen.getByTestId("token")).toHaveTextContent("test-invitation"),
  );
});

it("reads query invitation tokens even if an embedded browser drops or replaces the fragment", () => {
  window.history.replaceState(
    null,
    "",
    "/join?token=test-invitation&fbclid=tracking#_=_",
  );
  render(
    <BrowserRouter>
      <Form />
    </BrowserRouter>,
  );
  expect(screen.getByTestId("token")).toHaveTextContent("test-invitation");
  expect(window.location.search).toBe("");
  expect(window.location.hash).toBe("");
});

it("does not accept query tokens for reset or setup grants", () => {
  function ResetForm() {
    return <output data-testid="token">{useAuthLinkToken()}</output>;
  }
  window.history.replaceState(null, "", "/reset-password?token=ignored");
  render(
    <BrowserRouter>
      <ResetForm />
    </BrowserRouter>,
  );
  expect(screen.getByTestId("token")).toBeEmptyDOMElement();
  expect(window.location.search).toBe("");
});
