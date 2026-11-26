import { useId } from "react";

export function CostField({
  value,
  onChange,
  disabled,
  optional = false,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  optional?: boolean;
}) {
  const id = useId();
  return (
    <div className="form-field">
      <label htmlFor={id}>Koszt spotkania (PLN)</label>
      <input
        id={id}
        name="meeting-cost"
        aria-describedby={optional ? id + "-hint" : undefined}
        inputMode="decimal"
        pattern="[0-9]{1,6}([.,][0-9]{1,2})?|1000000([.,]0{1,2})?"
        required={!optional}
        disabled={disabled}
        value={value}
        placeholder={optional ? "Koszt z serii" : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {optional && (
        <small id={id + "-hint"}>
          Wyczyść pole, aby przywrócić koszt domyślny. Wpisz 0, jeśli spotkanie
          jest bezpłatne.
        </small>
      )}
    </div>
  );
}
