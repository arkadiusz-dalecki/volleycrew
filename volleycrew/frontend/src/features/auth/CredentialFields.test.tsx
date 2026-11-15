import { useState } from "react";
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { PasswordField, UsernameField } from "./CredentialFields";

afterEach(cleanup);
function PasswordExample() {
  const [value, setValue] = useState("");
  return (
    <PasswordField label="Hasło" value={value} onChange={setValue} fresh />
  );
}
it("counts Unicode code points and preserves password whitespace", () => {
  render(<PasswordExample />);
  const input = screen.getByLabelText("Hasło") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "🏐".repeat(7) } });
  expect(input.validationMessage).toContain("8");
  for (const value of ["abcdefgh", "12345678", "🏐".repeat(8)]) {
    fireEvent.change(input, { target: { value } });
    expect(input.validationMessage).toBe("");
  }
  fireEvent.change(input, { target: { value: "🏐".repeat(128) } });
  expect(input.validationMessage).toBe("");
  expect(input.value).toBe("🏐".repeat(128));
  fireEvent.change(input, { target: { value: "🏐".repeat(129) } });
  expect(input.validationMessage).toContain("128");
  const phrase = "  długa fraza ze spacjami  ";
  fireEvent.change(input, { target: { value: phrase } });
  expect(input.value).toBe(phrase);
  expect(input.validationMessage).toBe("");
});
it("username supports browser autofill without automatic capitalization", () => {
  render(<UsernameField value="arek.d" onChange={() => {}} />);
  const input = screen.getByLabelText("Login");
  expect(input).toHaveAttribute("autocomplete", "username");
  expect(input).toHaveAttribute("autocapitalize", "none");
  expect(input).toHaveAttribute("maxlength", "32");
});
