import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { HistoryFilters, HistoryItem } from "../../api/types";
import { formatDate, formatDayLong, formatDecimal, formatMoney } from "../../format";
import { AccountSelect } from "../../ui/AccountPicker";
import { Money } from "../../ui/Amount";
import { Confirm, Field, FormError, formErrors, useInvalidateAfterSave } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { TYPE_OPTIONS, entryLabel, entryLead, groupByDay } from "./model";
import styles from "./History.module.css";

function useDebounced(value: string, ms = 300): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

function subtitle(item: HistoryItem): string {
  const parts = [item.name ? entryLabel(item) : null, item.account_name];
  if (item.quantity && item.kind === "transaction") {
    // a unit price stays visible with hidden amounts (plan 8a)
    const at = item.price ? ` po ${formatMoney(item.price, { currency: item.price_currency, visible: true })}` : "";
    parts.push(`${formatDecimal(item.quantity, 8)} szt.${at}`);
  }
  if (item.quantity && item.kind !== "transaction") parts.push(`${formatDecimal(item.quantity, 0)} szt.`);
  if (item.tax) parts.push(`podatek ${formatMoney(item.tax)}`);
  if (item.note) parts.push(item.note);
  return parts.filter(Boolean).join(", ");
}

function deleteRequest(item: HistoryItem): Promise<void> {
  const target = item.delete!;
  if (target.target === "transaction") return api.deleteTransaction(target.id);
  if (target.target === "bond") return api.deleteBond(target.id);
  return api.deleteSavingsFlow(item.account_id, target.id);
}

export function HistoryScreen() {
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  const [type, setType] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [search, setSearch] = useState("");
  const q = useDebounced(search.trim());
  const filters: HistoryFilters = { account_ids: accountIds, type: type || null, from: from || null, to: to || null, q };
  const invalidate = useInvalidateAfterSave();
  const [deleting, setDeleting] = useState<HistoryItem | null>(null);
  const [error, setError] = useState<{ id: string; message: string } | null>(null);

  const entries = useInfiniteQuery({
    queryKey: keys.entries(filters),
    queryFn: ({ pageParam }) => api.entries(filters, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    enabled: ready,
  });
  const remove = useMutation({
    mutationFn: deleteRequest,
    onSuccess: async () => { await invalidate(); setDeleting(null); },
    onError: (err, item) => {
      setDeleting(null);
      setError({ id: item.id, message: formErrors(err).general ?? "Nie udało się usunąć wpisu. Spróbuj ponownie." });
    },
  });

  const items = entries.data?.pages.flatMap((page) => page.items) ?? [];

  function askToDelete(item: HistoryItem) { setError(null); setDeleting(item); }
  function cancelDelete() { setError(null); setDeleting(null); }
  function confirmDelete(item: HistoryItem) { setError(null); remove.mutate(item); }

  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Historia</h1>
      <div className={styles.filters}>
        {(accounts.data?.length ?? 0) > 0 && <AccountSelect accounts={accounts.data!} value={accountIds} onChange={setAccountIds} />}
        <div className={`${styles.filterRow} ${forms.form}`}>
          <Field id="history-type" label="Rodzaj">
            <select id="history-type" value={type} onChange={(e) => setType(e.target.value)}>
              {TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </Field>
          <Field id="history-from" label="Od"><input id="history-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
          <Field id="history-to" label="Do"><input id="history-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} /></Field>
        </div>
        <div className={forms.form}>
          <Field id="history-search" label="Szukaj">
            <input id="history-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Instrument, seria, konto lub opis" />
          </Field>
        </div>
      </div>

      {entries.isPending ? <Skeleton rows={6} />
        : entries.isError ? <ErrorState error={entries.error} onRetry={() => void entries.refetch()} />
          : items.length === 0 ? <EmptyState title="Brak wpisów dla wybranych filtrów." />
            : groupByDay(items).map((day) => (
              <section key={day.date} className={styles.day} aria-label={formatDate(day.date)}>
                <h2 className={styles.dayTitle}>{`${formatDayLong(day.date)} ${day.date.slice(0, 4)}`}</h2>
                <ul className={styles.list}>
                  {day.items.map((item) => (
                    <li key={item.id} className={styles.item}>
                      <div className={styles.row}>
                      <span className={styles.lead}>{entryLead(item)}</span>
                      <span className={styles.name}>
                        <b>{item.name ?? entryLabel(item)}</b>
                        <small>{subtitle(item)}</small>
                      </span>
                      <span className={styles.amount}>
                        <Money value={item.amount} sign tone currency={item.currency === "PLN" ? undefined : item.currency} />
                        {item.delete && (
                          <button type="button" className={forms.link} disabled={remove.isPending} onClick={() => askToDelete(item)}>Usuń</button>
                        )}
                      </span>
                      </div>
                      {deleting?.id === item.id && (
                        <Confirm
                          question={`Usunąć: ${entryLabel(item)} ${formatMoney(item.amount.replace("-", ""), { currency: item.currency === "PLN" ? "zł" : item.currency })} z ${formatDate(item.date)}?`}
                          confirmLabel="Usuń" busy={remove.isPending} onConfirm={() => confirmDelete(item)} onCancel={cancelDelete}
                        />
                      )}
                      {error?.id === item.id && <FormError message={error.message} />}
                    </li>
                  ))}
                </ul>
              </section>
            ))}

      {entries.hasNextPage && (
        <button type="button" className={`${ui.secondary} ${styles.more}`} disabled={entries.isFetchingNextPage}
          onClick={() => void entries.fetchNextPage()}>
          Pokaż więcej
        </button>
      )}
    </div>
  );
}
