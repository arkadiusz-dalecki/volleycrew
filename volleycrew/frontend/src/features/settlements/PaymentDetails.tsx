import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { api, message, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";

export function PaymentDetails() {
  const query = useQuery({
    queryKey: ["payment-details"],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/api/v1/me/payment-details", { signal })),
  });
  return (
    <section className="card">
      <h2>Dane do otrzymywania wpłat</h2>
      {query.isPending && <p role="status">Wczytujemy dane do wpłat…</p>}
      {query.isError && (
        <p role="alert">
          {message(query.error)}{" "}
          <button className="button" onClick={() => void query.refetch()}>
            Ponów
          </button>
        </p>
      )}
      {query.data && (
        <DetailsForm key={JSON.stringify(query.data)} details={query.data} />
      )}
    </section>
  );
}

function DetailsForm({
  details,
}: {
  details: components["schemas"]["PaymentDetails"];
}) {
  const id = useId();
  const client = useQueryClient();
  const [phone, setPhone] = useState(details.blik_phone ?? "");
  const [link, setLink] = useState(details.revolut_link ?? "");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    try {
      const saved = unwrap(
        await api.PUT("/api/v1/me/payment-details", {
          body: { blik_phone: phone || null, revolut_link: link || null },
        }),
      );
      setPhone(saved.blik_phone ?? "");
      setLink(saved.revolut_link ?? "");
      await client.invalidateQueries({ queryKey: ["settlements"] });
      setNotice("Dane do wpłat zapisane.");
    } catch (error) {
      setNotice(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form
      method="post"
      onSubmit={(event) => void save(event)}
      aria-label="Dane do wpłat"
    >
      <label className="form-field" htmlFor={id + "-phone"}>
        Numer telefonu BLIK
        <input
          id={id + "-phone"}
          name="blik-phone"
          type="tel"
          autoComplete="tel"
          maxLength={30}
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          disabled={busy}
        />
      </label>
      <label className="form-field" htmlFor={id + "-link"}>
        Link Revolut.me
        <input
          id={id + "-link"}
          name="revolut-link"
          type="url"
          autoCapitalize="none"
          spellCheck={false}
          maxLength={200}
          value={link}
          onChange={(event) => setLink(event.target.value)}
          disabled={busy}
        />
      </label>
      <button className="button primary" disabled={busy}>
        Zapisz metody wpłat
      </button>
      <p className="form-notice" role="status">
        {notice}
      </p>
    </form>
  );
}
