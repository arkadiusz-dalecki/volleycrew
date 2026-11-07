import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../../lib/api/client";

export function useSession() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async ({ signal }) => {
      const result = await api.GET("/api/v1/me", { signal });
      if (result.response.status === 401) return null;
      return unwrap(result);
    },
    refetchInterval: 30_000,
    staleTime: 10_000,
    retry: 1,
  });
}
