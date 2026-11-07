export const priorityLabel = (value: string) =>
  ({ founder: "Założyciel", player: "Zawodnik", guest: "Gość" })[value] ??
  value;
