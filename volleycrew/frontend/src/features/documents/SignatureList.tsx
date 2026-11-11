import { PdfViewer } from "./PdfViewer";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, Printer, RefreshCw } from "lucide-react";
import { api, message, unwrap } from "../../lib/api/client";

async function fetchPdf(
  meetingId: string,
  signal?: AbortSignal,
  download = false,
) {
  const result = await api.GET(
    "/api/v1/admin/meetings/{meeting_id}/signature-list",
    {
      params: { path: { meeting_id: meetingId }, query: { download } },
      parseAs: "blob",
      signal,
    },
  );
  const blob = unwrap(result);
  const filename =
    result.response.headers
      .get("Content-Disposition")
      ?.match(/filename="([^"]+)"/)?.[1] ?? "lista-podpisow.pdf";
  return {
    blob,
    filename,
    revision: Number(result.response.headers.get("X-Attendance-Revision")),
    version: Number(result.response.headers.get("X-Meeting-Version")),
    basis: result.response.headers.get("X-List-Basis"),
  };
}

export function SignatureListButton({
  meetingId,
  ready,
}: {
  meetingId: string;
  ready: boolean;
}) {
  const navigate = useNavigate();
  return (
    <button
      className="button small signature-list-button"
      onClick={() => navigate(`/admin/meetings/${meetingId}/signature-list`)}
      title={
        ready
          ? "Podgląd i pobranie aktualnej listy"
          : "Wydrukuj listę z potwierdzonych zapisów przed spotkaniem"
      }
    >
      <Printer size={17} /> Lista podpisów
    </button>
  );
}

function Preview({ meetingId }: { meetingId: string }) {
  const client = useQueryClient();
  const controller = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => () => controller.current?.abort(), []);
  const attendance = useQuery({
    queryKey: ["attendance", meetingId],
    staleTime: 0,
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/admin/meetings/{meeting_id}/attendance", {
          params: { path: { meeting_id: meetingId } },
          signal,
        }),
      ),
    refetchInterval: 30_000,
  });
  const pdf = useQuery({
    queryKey: ["signature-list", meetingId],
    queryFn: ({ signal }) => fetchPdf(meetingId, signal),
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
  const stale =
    !!pdf.data &&
    !!attendance.data &&
    pdf.data.version !== attendance.data.version;
  async function download() {
    if (busy) return;
    controller.current = new AbortController();
    setBusy(true);
    setError("");
    try {
      const document = await fetchPdf(
        meetingId,
        controller.current.signal,
        true,
      );
      client.setQueryData(["signature-list", meetingId], document);
      const objectUrl = URL.createObjectURL(document.blob);
      const link = window.document.createElement("a");
      link.href = objectUrl;
      link.download = document.filename;
      window.document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 30_000);
      await client.invalidateQueries({ queryKey: ["attendance", meetingId] });
    } catch (e) {
      if (!controller.current.signal.aborted) setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="text-link back-link" to={`/meetings/${meetingId}`}>
        <ArrowLeft size={16} /> Wróć do spotkania
      </Link>
      <div className="page-heading">
        <h1>Lista podpisów</h1>
        <p>Lista do wydruku przed spotkaniem lub z zatwierdzonej obecności.</p>
      </div>
      <section className="card signature-preview">
        <p className="form-note">
          {pdf.data?.basis === "attendance"
            ? "Źródło: zatwierdzona faktyczna obecność."
            : "Źródło: aktualne potwierdzone zapisy. Rezerwa i osoby oczekujące na potwierdzenie nie trafiają na listę. Wydruk nie zatwierdza obecności."}{" "}
          Numer, imię i nazwisko oraz miejsce na podpis. Drukuj na papierze A4 w
          skali 100%.
        </p>
        <div className="room-actions">
          <button
            className="button primary"
            disabled={busy || pdf.isFetching}
            onClick={() => void download()}
          >
            <Download size={17} />
            {busy ? "Przygotowujemy PDF…" : "Pobierz aktualny PDF"}
          </button>
          <button
            className="button"
            disabled={busy || pdf.isFetching}
            onClick={() => {
              setError("");
              void pdf.refetch();
              void attendance.refetch();
            }}
          >
            <RefreshCw size={17} /> Odśwież podgląd
          </button>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {stale && (
          <p className="form-error" role="alert">
            Dane spotkania zmieniły się po wygenerowaniu podglądu. Odśwież go,
            aby zobaczyć aktualną listę. Pobranie zawsze tworzy aktualny PDF.
          </p>
        )}
        {attendance.isError && (
          <p className="form-error" role="alert">
            Nie możemy sprawdzić, czy lista uczestników się zmieniła. Przed
            wydrukiem odśwież podgląd.
          </p>
        )}
        {pdf.isFetching ? (
          <p role="status">Generujemy podgląd listy…</p>
        ) : pdf.isError ? (
          <p className="form-error" role="alert">
            {message(pdf.error)} Użyj „Odśwież podgląd”, aby spróbować ponownie.
          </p>
        ) : (
          pdf.data && <PdfViewer blob={pdf.data.blob} />
        )}
      </section>
    </>
  );
}

export function SignatureListPage() {
  const { meetingId } = useParams();
  return meetingId ? <Preview key={meetingId} meetingId={meetingId} /> : null;
}
