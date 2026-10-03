import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { JournalEntry } from "../../api/types";
import { formatDate, todayIso } from "../../format";
import { EntryForm, type EntryDraft } from "../../notes/EntryForm";
import { PORTFOLIO, byMonth, choiceLabel, linkPath, moveBody, targetBody } from "../../notes/model";
import notes from "../../notes/Notes.module.css";
import { BackLink } from "../../ui/BackLink";
import { Field } from "../../ui/forms";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import styles from "./Journal.module.css";

const ALL = "all";
const EMPTY = "Zapisuj, dlaczego kupujesz i sprzedajesz — za rok to bezcenne.";

function Row({ entry, onEdit }: { entry: JournalEntry; onEdit: () => void }) {
  const target = entry.target;
  const path = target ? linkPath(target.link) : null;
  const label = target ? target.label : "Portfel";
  return (
    <div className={styles.row}>
      <span className={`num dim ${notes.date}`}>{formatDate(entry.entry_date).slice(0, 5)}</span>
      <div className={styles.body}>
        <span className={styles.labels}>
          {path ? <Link className={styles.label} to={path}>{label}</Link>
            : <span className={target ? styles.label : `${styles.label} ${styles.portfolio}`}>{label}</span>}
          {target?.closed && <small className="dim">zamknięty</small>}
        </span>
        <button type="button" className={notes.entryBody} title="Edytuj wpis" onClick={onEdit}>{entry.body}</button>
      </div>
    </div>
  );
}

/** Ustawienia → Dziennik (plan 7f-2): every journal entry, about holdings and the portfolio, newest first. */
export function JournalScreen() {
  const [params, setParams] = useSearchParams();
  const filter = params.get("target") ?? ALL;
  const queryClient = useQueryClient();
  const journal = useQuery({ queryKey: keys.journal(filter), queryFn: () => api.journal(filter === ALL ? null : filter) });
  const choices = useQuery({ queryKey: keys.journalTargets, queryFn: api.journalTargets });
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.portfolio });
  const add = useMutation({
    mutationFn: (draft: EntryDraft) => api.addEntry({ ...targetBody(draft.target), entry_date: draft.entry_date, body: draft.body }),
    onSuccess: async () => { setAdding(false); await refresh(); },
  });
  const update = useMutation({
    mutationFn: ({ entry, draft }: { entry: JournalEntry; draft: EntryDraft }) => api.updateEntry(entry.id, {
      entry_date: draft.entry_date, body: draft.body,
      // Only a changed holding is sent: resending a series without bonds would be refused.
      ...(draft.target !== (entry.target?.key ?? PORTFOLIO) ? moveBody(draft.target) : {}),
    }),
    onSuccess: async () => { setEditing(null); await refresh(); },
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteEntry(id),
    onSuccess: async () => { setEditing(null); await refresh(); },
  });
  const holdings = choices.data ?? [];
  const knownFilter = filter === ALL || filter === PORTFOLIO || holdings.some((c) => c.key === filter);

  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      <h1 className={ui.pageTitle}>Dziennik</h1>
      <div className={styles.toolbar}>
        <Field id="journal-filter" label="Pokaż">
          <select id="journal-filter" value={filter}
            onChange={(e) => setParams(e.target.value === ALL ? {} : { target: e.target.value }, { replace: true })}>
            <option value={ALL}>Wszystkie</option>
            <option value={PORTFOLIO}>Portfel</option>
            {!knownFilter && <option value={filter}>{filter}</option>}
            {holdings.map((c) => <option key={c.key} value={c.key}>{choiceLabel(c)}</option>)}
          </select>
        </Field>
        <button type="button" className={ui.primaryButton} aria-expanded={adding} onClick={() => setAdding(!adding)}>+ Wpis</button>
      </div>
      {adding && (
        <EntryForm id="journal-new" choices={holdings} busy={add.isPending} error={add.error}
          initial={{ entry_date: todayIso(), body: "", target: filter === ALL ? PORTFOLIO : filter }}
          onSave={(draft) => add.mutate(draft)} onCancel={() => setAdding(false)} />
      )}
      {journal.isPending ? <Skeleton rows={3} />
        : journal.isError ? <ErrorState error={journal.error} onRetry={() => void journal.refetch()} />
        : journal.data.entries.length === 0 ? <EmptyState title={EMPTY} />
        : byMonth(journal.data.entries).map((group) => (
          <section key={group.month} className={ui.section} aria-label={group.month}>
            <h2 className={styles.month}>{group.month}</h2>
            <ul className={notes.entries}>
              {group.entries.map((entry) => (
                <li key={entry.id}>
                  {editing === entry.id ? (
                    <EntryForm id={`journal-${entry.id}`} choices={holdings} targetLabel={entry.target?.label}
                      initial={{ entry_date: entry.entry_date, body: entry.body, target: entry.target?.key ?? PORTFOLIO }}
                      busy={update.isPending || remove.isPending} error={update.error ?? remove.error}
                      onSave={(draft) => update.mutate({ entry, draft })} onCancel={() => setEditing(null)}
                      onDelete={() => remove.mutate(entry.id)} />
                  ) : <Row entry={entry} onEdit={() => setEditing(entry.id)} />}
                </li>
              ))}
            </ul>
          </section>
        ))}
    </div>
  );
}
