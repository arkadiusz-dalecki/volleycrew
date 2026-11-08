const formatter = new Intl.NumberFormat("pl-PL", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
export function points(value: string | number) {
  const n = Number(value);
  return formatter.format(Math.abs(n) < 0.05 ? 0 : n);
}
export function delta(value: string | number) {
  return `${Number(value) >= 0.05 ? "+" : ""}${points(value)}`;
}

export function rankedMeetings(count: number) {
  if (count === 1) return "1 spotkanie rankingowe";
  const few =
    count % 10 >= 2 &&
    count % 10 <= 4 &&
    !(count % 100 >= 12 && count % 100 <= 14);
  return `${count} ${few ? "spotkania rankingowe" : "spotkań rankingowych"}`;
}
