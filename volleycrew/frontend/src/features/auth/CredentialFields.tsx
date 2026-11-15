import { useId } from "react";

export function UsernameField({
  value,
  onChange,
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const hint = useId();
  return (
    <label className="form-field">
      Login
      <input
        aria-label="Login"
        aria-describedby={hint}
        name="username"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="username"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        minLength={3}
        maxLength={32}
        pattern="[A-Za-z0-9][A-Za-z0-9._\-]{2,31}"
        required
        disabled={disabled}
      />
      <small id={hint}>
        3–32 litery bez polskich znaków, cyfry, kropka, myślnik lub
        podkreślenie.
      </small>
    </label>
  );
}

export function PasswordField({
  label,
  value,
  onChange,
  fresh = false,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  fresh?: boolean;
  disabled?: boolean;
}) {
  const hint = useId();
  return (
    <label className="form-field">
      {label}
      <input
        aria-label={label}
        aria-describedby={fresh ? hint : undefined}
        type="password"
        name={fresh ? "new-password" : "password"}
        value={value}
        onChange={(e) => {
          const value = e.target.value;
          const length = Array.from(value).length;
          e.target.setCustomValidity(
            length > 128 || (fresh && length < 8)
              ? fresh
                ? "Hasło musi mieć od 8 do 128 znaków."
                : "Hasło może mieć najwyżej 128 znaków."
              : "",
          );
          onChange(value);
        }}
        autoComplete={fresh ? "new-password" : "current-password"}
        minLength={fresh ? 8 : 1}
        maxLength={256}
        required
        disabled={disabled}
      />
      {fresh && (
        <small id={hint}>
          8–128 znaków. Możesz użyć frazy ze spacjami i polskimi znakami.
        </small>
      )}
    </label>
  );
}
