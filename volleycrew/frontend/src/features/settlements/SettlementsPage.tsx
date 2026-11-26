import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Check } from "lucide-react";
import { Link, useHref } from "react-router-dom";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useAdminView } from "../auth/ViewMode";
import { api, message, unwrap } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { dateLabel, localDate } from "../meetings/dates";
import { money } from "./money";

const status = {
  paid: "Opłacone",
  pending: "Czeka na potwierdzenie",
  rejected: "Odrzucone",
};
type Account = components["schemas"]["PlayerSettlements"];
type Recipient = components["schemas"]["Recipient"];
type Selection = components["schemas"]["ReportPayment"];
type Review = components["schemas"]["ReviewPayment"];

function useMySettlements() {
  return useQuery({
    queryKey: ["settlements", "mine"],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/api/v1/me/settlements", { signal })),
    refetchInterval: 30_000,
  });
}

export function SettlementsPage() {
  const query = useMySettlements();
  const adminView = useAdminView();
  return (
    <>
      <div className="page-heading settlement-heading">
        <h1>Rozliczenia</h1>
        {adminView && (
          <Link className="button" to="/admin/settlements">
            Rozliczenia ekipy
          </Link>
        )}
      </div>
      {query.isPending && <p role="status">Wczytujemy rozliczenia…</p>}
      {query.isError && (
        <p role="alert">
          {message(query.error)}{" "}
          <button className="button" onClick={() => void query.refetch()}>
            Ponów
          </button>
        </p>
      )}
      {query.data && (
        <AccountSection account={query.data} recipient={query.data.recipient} />
      )}
    </>
  );
}

export function AdminSettlementsPage() {
  const query = useQuery({
    queryKey: ["settlements", "admin"],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/api/v1/admin/settlements", { signal })),
    refetchInterval: 30_000,
  });
  const accounts = query.data
    ?.filter((account) => account.charges.length || account.reports.length)
    .sort((a, b) => b.pending - a.pending || b.due - a.due);
  return (
    <>
      <div className="page-heading">
        <h1>Rozliczenia ekipy</h1>
      </div>
      {query.isPending && <p role="status">Wczytujemy rozliczenia…</p>}
      {query.isError && (
        <p role="alert">
          {message(query.error)}{" "}
          <button className="button" onClick={() => void query.refetch()}>
            Ponów
          </button>
        </p>
      )}
      {accounts?.length === 0 && <p>Brak opłat i wpłat do rozliczenia.</p>}
      {!!accounts?.length && <TeamSettlementSummary accounts={accounts} />}
      {accounts?.map((account) => (
        <AccountSection key={account.player_id} account={account} admin />
      ))}
    </>
  );
}

function accountHeadingId(playerId: string) {
  return `settlement-player-${playerId}`;
}

function TeamSettlementSummary({ accounts }: { accounts: Account[] }) {
  const dashboard = useHref("/admin/settlements");
  const rows = accounts.map((account) => ({
    playerId: account.player_id,
    name: account.name,
    due: account.due,
    pending: account.pending,
    paid: account.reports.reduce(
      (total, report) => total + (report.status === "paid" ? report.amount : 0),
      0,
    ),
  }));
  const totals = rows.reduce(
    (total, row) => ({
      due: total.due + row.due,
      pending: total.pending + row.pending,
      paid: total.paid + row.paid,
    }),
    { due: 0, pending: 0, paid: 0 },
  );
  return (
    <section className="settlement-card settlement-summary">
      <h2 id="team-settlement-summary">Podsumowanie rozliczeń</h2>
      <div
        className="settlement-table-scroll settlement-summary-scroll"
        role="region"
        aria-labelledby="team-settlement-summary"
        tabIndex={0}
      >
        <table
          className="settlement-table settlement-summary-table"
          aria-labelledby="team-settlement-summary"
        >
          <thead>
            <tr>
              <th scope="col">Osoba</th>
              <th scope="col">Do zapłaty</th>
              <th scope="col">Zgłoszone</th>
              <th scope="col">Wpłacono</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.playerId}>
                <th scope="row">
                  <a href={`${dashboard}#${accountHeadingId(row.playerId)}`}>
                    {row.name}
                  </a>
                </th>
                <td>{money(row.due)}</td>
                <td>{money(row.pending)}</td>
                <td>{money(row.paid)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Razem</th>
              <td>{money(totals.due)}</td>
              <td>{money(totals.pending)}</td>
              <td>{money(totals.paid)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

function AccountSection({
  account,
  admin = false,
  recipient,
}: {
  account: Account;
  admin?: boolean;
  recipient?: Recipient | null;
}) {
  const client = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const attempt = useRef<Selection | null>(null);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [reviewId, setReviewId] = useState("");
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState("");
  const available = account.charges.filter((charge) => charge.due > 0);
  const chosen = available.filter((charge) =>
    selected.includes(charge.meeting_id),
  );
  const amount = chosen.reduce((total, charge) => total + charge.due, 0);
  const submit = useMutation({
    mutationFn: async (body: Selection) => {
      const response = admin
        ? await api.POST(
            "/api/v1/admin/settlements/players/{player_id}/payments",
            {
              params: { path: { player_id: account.player_id } },
              body,
            },
          )
        : await api.POST("/api/v1/me/settlements/payments", { body });
      if (!response.response.ok) unwrap(response);
    },
    onSuccess: async () => {
      setSelected([]);
      attempt.current = null;
      setPaymentOpen(false);
      setNotice(
        admin ? "Wpłata zapisana." : "Wpłata zgłoszona do potwierdzenia.",
      );
      await client.invalidateQueries({ queryKey: ["settlements"] });
    },
    onError: async () =>
      client.invalidateQueries({ queryKey: ["settlements"] }),
  });
  const review = useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Review }) => {
      const result = await api.POST(
        "/api/v1/admin/settlements/payments/{report_id}",
        {
          params: { path: { report_id: id } },
          body,
        },
      );
      if (!result.response.ok) unwrap(result);
    },
    onSuccess: async () => {
      setReviewId("");
      setReason("");
      setNotice("Zapisano decyzję o wpłacie.");
      await client.invalidateQueries({ queryKey: ["settlements"] });
    },
    onError: async () =>
      client.invalidateQueries({ queryKey: ["settlements"] }),
  });
  function selectCharge(id: string, checked: boolean) {
    setSelected((current) =>
      checked ? [...current, id] : current.filter((value) => value !== id),
    );
  }
  function payAll() {
    setSelected(available.map((charge) => charge.meeting_id));
    openPayment();
  }
  function openPayment() {
    setPaymentOpen(true);
    submit.reset();
  }
  function report(event: FormEvent) {
    event.preventDefault();
    if (!amount || submit.isPending) return;
    setNotice("");
    const ids = chosen.map((charge) => charge.meeting_id);
    if (
      !attempt.current ||
      attempt.current.amount !== amount ||
      attempt.current.meeting_ids.join() !== ids.join()
    ) {
      attempt.current = { id: crypto.randomUUID(), amount, meeting_ids: ids };
    }
    submit.mutate(attempt.current);
  }
  const openPaymentButton = amount > 0 && (
    <button
      type="button"
      className={`button primary${admin ? " settlement-open-payment" : ""}`}
      disabled={submit.isPending}
      onClickCapture={(event) => event.currentTarget.focus()}
      onClick={openPayment}
    >
      {admin ? "Zapisz wpłatę" : "Przejdź do płatności"} · {money(amount)}
    </button>
  );
  return (
    <section className="card settlement-card">
      <h2
        id={admin ? accountHeadingId(account.player_id) : undefined}
        tabIndex={admin ? -1 : undefined}
      >
        {admin ? account.name : "Moje saldo"}
      </h2>
      <dl className="settlement-totals">
        <div>
          <dt>Do zapłaty</dt>
          <dd>{money(account.due)}</dd>
        </div>
        <div>
          <dt>Czeka na potwierdzenie</dt>
          <dd>{money(account.pending)}</dd>
        </div>
        {account.credit > 0 && (
          <div>
            <dt>Nadpłata</dt>
            <dd>{money(account.credit)}</dd>
          </div>
        )}
      </dl>
      {account.oldest_due_at && (
        <p>Najstarsza opłata od {dateLabel(account.oldest_due_at)}.</p>
      )}
      {account.reminder && (
        <p className="form-notice">Zaległość wymaga rozliczenia.</p>
      )}
      {account.charges.length > 0 && (
        <div className="settlement-charge-form">
          {!admin && available.length > 0 && (
            <div className="row-actions settlement-charge-actions">
              <button
                type="button"
                className="button settlement-pay-all"
                disabled={submit.isPending}
                onClickCapture={(event) => event.currentTarget.focus()}
                onClick={payAll}
              >
                Zapłać wszystko · {money(account.due)}
              </button>
              {chosen.length < available.length && openPaymentButton}
            </div>
          )}
          <div
            className="settlement-table-scroll"
            role="region"
            aria-label="Opłaty za spotkania"
            tabIndex={0}
          >
            <table
              className="settlement-table settlement-charges-table"
              aria-label="Opłaty za spotkania"
            >
              <thead>
                <tr>
                  <th scope="col">Spotkanie</th>
                  <th scope="col">Kwota</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {account.charges.map((charge) => {
                  const checked =
                    charge.due > 0 && selected.includes(charge.meeting_id);
                  const selectable = charge.due > 0 && !submit.isPending;
                  const day = localDate(charge.starts_at)
                    .split("-")
                    .reverse()
                    .join(".");
                  const date = <time dateTime={charge.starts_at}>{day}</time>;
                  return (
                    <tr
                      key={charge.meeting_id}
                      data-selected={checked || undefined}
                      data-selectable={selectable || undefined}
                      onClick={
                        selectable
                          ? (event) => {
                              if (
                                event.target instanceof Element &&
                                !event.target.closest("button")
                              ) {
                                selectCharge(charge.meeting_id, !checked);
                              }
                            }
                          : undefined
                      }
                    >
                      <th scope="row">
                        {charge.due > 0 ? (
                          <button
                            type="button"
                            className="settlement-choice"
                            data-charge-id={charge.meeting_id}
                            aria-label={`Wybierz opłatę za ${day}`}
                            aria-pressed={checked}
                            disabled={submit.isPending}
                            onClick={() =>
                              selectCharge(charge.meeting_id, !checked)
                            }
                          >
                            <Check
                              className="settlement-checkmark"
                              size={16}
                              aria-hidden="true"
                            />
                            {date}
                          </button>
                        ) : (
                          <span className="settlement-date">{date}</span>
                        )}
                      </th>
                      <td>{money(charge.amount)}</td>
                      <td>
                        <ChargeStatus charge={charge} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {admin && openPaymentButton}
        </div>
      )}
      {paymentOpen && (
        <SettlementPaymentDialog
          amount={amount}
          admin={admin}
          recipient={recipient}
          busy={submit.isPending}
          error={submit.isError ? message(submit.error) : undefined}
          onReport={report}
          onClose={() => setPaymentOpen(false)}
        />
      )}
      {account.reports.length > 0 && (
        <details>
          <summary>Historia wpłat</summary>
          <ul className="settlement-list">
            {account.reports.map((item) => (
              <li key={item.id}>
                <p className="settlement-report-description">
                  {money(item.amount)} · {dateLabel(item.created_at)} ·{" "}
                  {status[item.status]}
                </p>
                {item.reason && <p>Powód: {item.reason}</p>}
                {admin && item.status === "pending" && (
                  <div className="row-actions settlement-review-actions">
                    <button
                      type="button"
                      className="button primary"
                      disabled={review.isPending}
                      onClick={() =>
                        review.mutate({ id: item.id, body: { status: "paid" } })
                      }
                    >
                      Potwierdź wpływ
                    </button>
                    <button
                      type="button"
                      className="button"
                      disabled={review.isPending}
                      onClick={() => {
                        setReviewId(item.id);
                        setReason("");
                      }}
                    >
                      Odrzuć zgłoszenie
                    </button>
                  </div>
                )}
                {reviewId === item.id && item.status === "pending" && (
                  <form
                    className="settlement-review-form"
                    method="post"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (reason.trim())
                        review.mutate({
                          id: item.id,
                          body: { status: "rejected", reason },
                        });
                    }}
                  >
                    <label className="form-field">
                      Powód odrzucenia
                      <textarea
                        name="reason"
                        value={reason}
                        maxLength={500}
                        required
                        onChange={(event) => setReason(event.target.value)}
                      />
                    </label>
                    <div className="row-actions">
                      <button
                        className="button primary"
                        disabled={review.isPending}
                      >
                        Potwierdź odrzucenie
                      </button>
                      <button
                        type="button"
                        className="button"
                        onClick={() => setReviewId("")}
                      >
                        Anuluj
                      </button>
                    </div>
                  </form>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
      <p role="status" className="form-notice">
        {notice}
      </p>
      {review.isError && <p role="alert">{message(review.error)}</p>}
    </section>
  );
}

function SettlementPaymentDialog({
  amount,
  admin,
  recipient,
  busy,
  error,
  onReport,
  onClose,
}: {
  amount: number;
  admin: boolean;
  recipient?: Recipient | null;
  busy: boolean;
  error?: string;
  onReport: (event: FormEvent) => void;
  onClose: () => void;
}) {
  const [confirmClose, setConfirmClose] = useState(false);
  const summary = useRef<HTMLParagraphElement>(null);
  const continueButton = useRef<HTMLButtonElement>(null);
  const closeDescription = useId();
  useEffect(() => {
    if (confirmClose) continueButton.current?.focus();
    else summary.current?.focus();
  }, [confirmClose]);

  function requestClose() {
    if (admin || confirmClose) onClose();
    else setConfirmClose(true);
  }
  return (
    <ConfirmDialog
      title={
        confirmClose
          ? "Zamknąć bez zgłoszenia?"
          : admin
            ? "Zapisz wpłatę"
            : "Płatność"
      }
      busy={busy}
      onDismiss={requestClose}
    >
      {confirmClose ? (
        <>
          <p id={closeDescription}>
            Możesz wrócić do płatności albo zamknąć okno i zgłosić wpłatę
            później.
          </p>
          <div className="row-actions">
            <button
              type="button"
              className="button primary"
              ref={continueButton}
              aria-describedby={closeDescription}
              onClick={() => setConfirmClose(false)}
            >
              Wróć do płatności
            </button>
            <button type="button" className="button" onClick={onClose}>
              Zamknij bez zgłoszenia
            </button>
          </div>
        </>
      ) : (
        <form
          className="settlement-payment-panel"
          method="post"
          onSubmit={onReport}
        >
          <p className="settlement-payment-amount" tabIndex={-1} ref={summary}>
            Wybrana kwota <strong>{money(amount)}</strong>
          </p>
          {recipient && <PaymentMethods recipient={recipient} />}
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          <div className="settlement-payment-submit">
            <button
              type="submit"
              className="button primary"
              disabled={busy || !amount}
            >
              {admin ? "Zapisz wpłatę" : "Zgłoś wpłatę"}
            </button>
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={requestClose}
            >
              Zamknij
            </button>
          </div>
        </form>
      )}
    </ConfirmDialog>
  );
}

function ChargeStatus({ charge }: { charge: Account["charges"][number] }) {
  const amounts = [
    { label: "Do zapłaty", value: charge.due, state: "due" },
    { label: "Do weryfikacji", value: charge.pending, state: "pending" },
    { label: status.paid, value: charge.paid, state: "paid" },
  ].filter(({ value }) => value > 0);
  if (!amounts.length)
    return <span className="settlement-status">Rozliczone</span>;
  return (
    <div className="settlement-statuses">
      {amounts.map(({ label, value, state }) => (
        <span className="settlement-status" data-state={state} key={state}>
          {label}
          {(amounts.length > 1 || value !== charge.amount) && (
            <> {money(value)}</>
          )}
        </span>
      ))}
    </div>
  );
}

function PaymentMethods({ recipient }: { recipient: Recipient }) {
  const id = useId();
  const phone = recipient.blik_phone;
  const [feedback, setFeedback] = useState("");
  const value = useRef<HTMLSpanElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  async function copy(number: string) {
    clearTimeout(timer.current);
    try {
      await navigator.clipboard.writeText(number);
      setFeedback("Numer skopiowany.");
    } catch {
      setFeedback("Skopiuj ręcznie numer wyświetlony powyżej.");
    }
    timer.current = setTimeout(() => setFeedback(""), 2500);
  }
  useEffect(() => {
    const element = value.current;
    if (!element || !phone || !("CommandEvent" in window)) return;
    const listener = () => void copy(phone);
    element.addEventListener("command", listener);
    return () => element.removeEventListener("command", listener);
  }, [phone]);
  useEffect(() => () => clearTimeout(timer.current), []);
  return (
    <>
      <p className="settlement-payment-recipient">
        Odbiorca <strong>{recipient.name}</strong>
        {phone && (
          <>
            {" "}
            ·{" "}
            <span ref={value} id={id}>
              {phone}
            </span>
          </>
        )}
      </p>
      <div>
        <div className="settlement-payment-methods">
          {recipient.revolut_link && (
            <a
              className="button"
              href={recipient.revolut_link}
              target="_blank"
              rel="noopener noreferrer"
            >
              Otwórz Revolut
            </a>
          )}
          {phone && (
            <button
              type="button"
              className="button"
              {...{ command: "--copy", commandfor: id }}
              onClick={() => {
                if (!("CommandEvent" in window)) void copy(phone);
              }}
            >
              Kopiuj numer BLIK
            </button>
          )}
        </div>
        <p role="status" className="settlement-copy-notice">
          {feedback}
        </p>
      </div>
    </>
  );
}
