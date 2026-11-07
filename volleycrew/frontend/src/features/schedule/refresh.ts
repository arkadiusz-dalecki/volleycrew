import type { QueryClient } from "@tanstack/react-query";
export async function refreshSchedule(client: QueryClient) {
  await Promise.all(
    [
      "admin-schedule",
      "calendar",
      "meeting",
      "next-meeting",
      "participation",
      "seat-offers",
      "attendance",
      "room-teams",
      "public-teams",
      "attendance-history",
      "signature-list",
      "result",
      "admin-result",
      "ranking",
      "results",
      "rating-history",
    ].map((key) => client.invalidateQueries({ queryKey: [key] })),
  );
}
