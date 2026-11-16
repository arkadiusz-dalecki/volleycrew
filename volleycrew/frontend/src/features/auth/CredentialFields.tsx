import { useEffect, useId, useRef, useState } from "react";
import { Eye, EyeOff } from "lucide-react";

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
  const id = useId();
  return (
    <div className="form-field">
      <label htmlFor={id}>Login</label>
      <input
        id={id}
        enterKeyHint="next"
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
    </div>
  );
}

export function PasswordField({
  label,
  value,
  onChange,
  fresh = false,
  disabled = false,
  match,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  fresh?: boolean;
  disabled?: boolean;
  match?: string;
}) {
  const id = useId();
  const hint = `${id}-hint`;
  const errorId = `${id}-error`;
  const input = useRef<HTMLInputElement>(null);
  const [visible, setVisible] = useState(false);
  const [showError, setShowError] = useState(false);
  const length = Array.from(value).length;
  const error =
    length > 128 || (fresh && length > 0 && length < 8)
      ? fresh
        ? "Hasło musi mieć od 8 do 128 znaków."
        : "Hasło może mieć najwyżej 128 znaków."
      : match !== undefined && value !== match && value.length > 0
        ? "Podane hasła muszą być takie same."
        : "";
  useEffect(() => {
    input.current?.setCustomValidity(error);
  }, [error]);
  const invalid = showError && Boolean(error);
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      {fresh && (
        <small id={hint}>
          8–128 znaków. Możesz użyć frazy ze spacjami i polskimi znakami.
        </small>
      )}
      <div className="password-control">
        <input
          ref={input}
          id={id}
          aria-describedby={
            [fresh ? hint : "", invalid ? errorId : ""]
              .filter(Boolean)
              .join(" ") || undefined
          }
          aria-invalid={invalid || undefined}
          type={visible ? "text" : "password"}
          name={
            match !== undefined
              ? "password-confirmation"
              : fresh
                ? "new-password"
                : "password"
          }
          value={value}
          onChange={(e) => {
            setShowError(false);
            onChange(e.target.value);
          }}
          onInvalid={() => setShowError(true)}
          autoComplete={fresh ? "new-password" : "current-password"}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="done"
          minLength={fresh ? 8 : 1}
          maxLength={256}
          required
          disabled={disabled}
        />
        <button
          type="button"
          className="button password-toggle"
          aria-label={`Pokaż hasło: ${label}`}
          aria-pressed={visible}
          aria-controls={id}
          disabled={disabled}
          onClick={() => setVisible(!visible)}
        >
          {visible ? (
            <EyeOff size={18} aria-hidden="true" />
          ) : (
            <Eye size={18} aria-hidden="true" />
          )}
          <span>Pokaż hasło</span>
        </button>
      </div>
      {invalid && (
        <p id={errorId} className="field-error" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
