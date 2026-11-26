const currency = new Intl.NumberFormat("pl-PL", {
  style: "currency",
  currency: "PLN",
});

export const money = (grosz: number) => currency.format(grosz / 100);
export const amountText = (grosz: number) => (grosz / 100).toFixed(2);
export function toGrosz(value: string) {
  const [whole, fraction = ""] = value.replace(",", ".").split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

export function splitShares(cost: number, ids: string[]) {
  const sorted = [...ids].sort();
  if (!sorted.length) return new Map<string, number>();
  const base = Math.floor(cost / sorted.length);
  const remainder = cost % sorted.length;
  return new Map(
    sorted.map((id, index) => [id, base + Number(index < remainder)]),
  );
}
