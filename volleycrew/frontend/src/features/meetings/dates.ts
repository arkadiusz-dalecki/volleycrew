export function localDate(value: string, zone = "Europe/Warsaw") {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  return ["year", "month", "day"]
    .map((type) => parts.find((part) => part.type === type)!.value)
    .join("-");
}
export function dateLabel(value: string, zone = "Europe/Warsaw") {
  return new Intl.DateTimeFormat("pl-PL", {
    timeZone: zone,
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(value));
}
export function hour(value: string, zone = "Europe/Warsaw") {
  return new Intl.DateTimeFormat("pl-PL", {
    timeZone: zone,
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
export function shiftMonth(month: string, shift: number) {
  const [year, number] = month.split("-").map(Number);
  const value = new Date(Date.UTC(year, number - 1 + shift, 1));
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, "0")}`;
}
export const statusLabel: Record<string, string> = {
  scheduled: "Zaplanowane",
  attendance_checked: "Obecność sprawdzona",
  teams_confirmed: "Drużyny gotowe",
  completed: "Zakończone",
  cancelled: "Odwołane",
};
