import { useQuery } from "@tanstack/react-query";
import { CircleCheck, CircleAlert, LoaderCircle, RotateCw } from "lucide-react";
import { api } from "../../lib/api/client";

export function ServiceStatus() {
  const status = useQuery({
    queryKey: ["system", "readiness"],
    queryFn: async ({ signal }) => {
      const { data, error } = await api.GET("/api/v1/health/ready", { signal });
      if (error || !data) throw new Error("not_ready");
      return data;
    },
    refetchInterval: 30_000,
  });

  if (status.isPending) {
    return (
      <div className="service-status" role="status">
        <LoaderCircle size={15} className="spin" /> Łączymy z usługą…
      </div>
    );
  }
  if (status.isError) {
    return (
      <div className="service-status offline" role="status">
        <CircleAlert size={15} />
        <span>Usługa chwilowo niedostępna</span>
        <button
          aria-label="Ponów połączenie"
          onClick={() => void status.refetch()}
          disabled={status.isFetching}
        >
          <RotateCw size={15} />
        </button>
      </div>
    );
  }
  return (
    <div className="service-status" role="status">
      <CircleCheck size={15} /> Połączenie z usługą działa
    </div>
  );
}
