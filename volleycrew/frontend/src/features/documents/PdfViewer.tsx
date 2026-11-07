import { useEffect, useRef, useState } from "react";
import type { PDFDocumentLoadingTask } from "pdfjs-dist";
import { ExternalLink } from "lucide-react";

/** Render the actual PDF locally, including on phones without an inline PDF plugin. */
export function PdfViewer({ blob }: { blob: Blob }) {
  const container = useRef<HTMLDivElement>(null);
  const link = useRef<HTMLAnchorElement>(null);
  const [rendered, setRendered] = useState<Blob | null>(null);
  const [error, setError] = useState<{ blob: Blob; message: string } | null>(
    null,
  );
  useEffect(() => {
    let cancelled = false;
    let task: PDFDocumentLoadingTask | undefined;
    const element = container.current!;
    element.replaceChildren();
    const url = URL.createObjectURL(blob);
    if (link.current) link.current.href = url;
    async function render() {
      const [pdfjs, worker] = await Promise.all([
        import("pdfjs-dist"),
        import("pdfjs-dist/build/pdf.worker.min.mjs?url"),
      ]);
      if (cancelled) return;
      pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
      task = pdfjs.getDocument({
        data: await blob.arrayBuffer(),
        disableWorkerRendering: true,
      });
      if (cancelled) {
        await task.destroy();
        return;
      }
      const document = await task.promise;
      for (let number = 1; number <= document.numPages; number++) {
        const page = await document.getPage(number);
        if (cancelled) return;
        const section = window.document.createElement("section");
        section.className = "signature-pdf-page";
        section.setAttribute("aria-label", `Strona ${number}`);
        const canvas = window.document.createElement("canvas");
        canvas.setAttribute("aria-hidden", "true");
        const viewport = page.getViewport({ scale: 2 });
        canvas.width = Math.ceil(viewport.width);
        canvas.height = Math.ceil(viewport.height);
        section.appendChild(canvas);
        element.appendChild(section);
        await page.render({ canvas, viewport }).promise;
        const text = await page.getTextContent();
        if (cancelled) return;
        const accessibleText = window.document.createElement("p");
        accessibleText.className = "signature-pdf-text";
        accessibleText.textContent = text.items
          .map((item) => ("str" in item ? item.str : ""))
          .join(" ");
        section.appendChild(accessibleText);
      }
      if (!cancelled) setRendered(blob);
    }
    void render().catch(() => {
      if (!cancelled)
        setError({
          blob,
          message:
            "Nie udało się wyświetlić PDF. Otwórz go w osobnej karcie lub pobierz dokument.",
        });
    });
    return () => {
      cancelled = true;
      URL.revokeObjectURL(url);
      void task?.destroy().catch(() => {});
    };
  }, [blob]);
  return (
    <>
      <a
        ref={link}
        target="_blank"
        rel="noopener noreferrer"
        className="text-link"
      >
        <ExternalLink size={16} /> Otwórz PDF w osobnej karcie
      </a>
      {error?.blob === blob ? (
        <p role="alert" className="form-error">
          {error.message}
        </p>
      ) : (
        rendered !== blob && <p role="status">Wyświetlamy PDF…</p>
      )}
      <div
        ref={container}
        className="signature-pdf-document"
        role="region"
        aria-label="Podgląd listy podpisów"
        data-rendered={rendered === blob}
      />
      <p className="form-note">
        Dokument można pobrać, a następnie wydrukować z przeglądarki PDF.
      </p>
    </>
  );
}
