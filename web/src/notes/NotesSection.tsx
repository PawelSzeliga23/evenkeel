import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api } from "../api/endpoints";
import { errorMessage } from "../api/messages";
import { keys } from "../api/queryKeys";
import type { HoldingNotes, NoteEntry } from "../api/types";
import { formatDate, todayIso } from "../format";
import { FormError } from "../ui/forms";
import forms from "../ui/forms.module.css";
import ui from "../ui/ui.module.css";
import { EntryForm, type EntryDraft } from "./EntryForm";
import { MAX_THESIS, NO_ENTRIES, RECENT, targetKey, type NoteTarget } from "./model";
import styles from "./Notes.module.css";

export function EntryRow({ entry, onEdit }: { entry: NoteEntry; onEdit: () => void }) {
  return (
    <div className={styles.entry}>
      <span className={`num dim ${styles.date}`}>{formatDate(entry.entry_date)}</span>
      <button type="button" className={styles.entryBody} title="Edytuj wpis" onClick={onEdit}>{entry.body}</button>
    </div>
  );
}

/** Sekcja „Notatki” in the position, bond and savings details: the holding's thesis and its newest journal entries. */
export function NotesSection({ notes, target, shared = true }: { notes: HoldingNotes; target: NoteTarget; shared?: boolean }) {
  const queryClient = useQueryClient();
  const key = targetKey(target);
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.portfolio });
  const [thesis, setThesis] = useState<string | null>(null); // null = not editing
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const saveThesis = useMutation({
    mutationFn: (body: string) => api.saveThesis(target, body),
    onSuccess: async () => { setThesis(null); await refresh(); },
  });
  const add = useMutation({
    mutationFn: (draft: EntryDraft) => api.addEntry({ ...target, entry_date: draft.entry_date, body: draft.body }),
    onSuccess: async () => { setAdding(false); await refresh(); },
  });
  const update = useMutation({
    mutationFn: ({ id, draft }: { id: number; draft: EntryDraft }) =>
      api.updateEntry(id, { entry_date: draft.entry_date, body: draft.body }),
    onSuccess: async () => { setEditing(null); await refresh(); },
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteEntry(id),
    onSuccess: async () => { setEditing(null); await refresh(); },
  });

  function submitThesis(event: FormEvent) {
    event.preventDefault();
    if (thesis !== null && !saveThesis.isPending) saveThesis.mutate(thesis.trim());
  }

  return (
    <section className={ui.section} aria-labelledby="section-Notatki">
      <h2 id="section-Notatki" className={ui.sectionTitle}>Notatki</h2>
      {shared && <p className={styles.shared}>wspólne dla wszystkich kont</p>}

      <div className={styles.block} role="group" aria-label="Teza">
        <div className={styles.blockHead}>
          <h3>Teza</h3>
          {notes.thesis && thesis === null && (
            <button type="button" className={forms.link} onClick={() => setThesis(notes.thesis!.body)}>Edytuj</button>
          )}
        </div>
        {thesis !== null ? (
          <form className={styles.form} onSubmit={submitThesis}>
            <label htmlFor="thesis-body" className="dim">Treść tezy</label>
            <textarea id="thesis-body" className={styles.text} rows={5} maxLength={MAX_THESIS} value={thesis}
              onChange={(e) => setThesis(e.target.value)} />
            {thesis.length > MAX_THESIS - 500 && <small className={styles.count}>{`${thesis.length}/${MAX_THESIS}`}</small>}
            <FormError message={saveThesis.isError ? errorMessage(saveThesis.error) : null} />
            <div className={forms.actions}>
              <button type="submit" className={ui.primaryButton} disabled={saveThesis.isPending}>Zapisz</button>
              <button type="button" className={forms.cancel} onClick={() => setThesis(null)}>Anuluj</button>
            </div>
          </form>
        ) : notes.thesis ? (
          <blockquote className={styles.thesis}>
            <p>{notes.thesis.body}</p>
            <small className="dim">{`zaktualizowano ${formatDate(notes.thesis.updated_at)}`}</small>
          </blockquote>
        ) : (
          <button type="button" className={styles.add} onClick={() => setThesis("")}>+ Dodaj tezę</button>
        )}
      </div>

      <div className={styles.block} role="group" aria-label="Dziennik">
        <div className={styles.blockHead}>
          <h3>Dziennik</h3>
          <button type="button" className={forms.link} aria-expanded={adding} onClick={() => setAdding(!adding)}>+ Wpis</button>
        </div>
        {adding && (
          <EntryForm id="new-entry" initial={{ entry_date: todayIso(), body: "", target: key }} busy={add.isPending}
            error={add.error} onSave={(draft) => add.mutate(draft)} onCancel={() => setAdding(false)} />
        )}
        {notes.recent.length === 0 && !adding && <p className="dim">{NO_ENTRIES}</p>}
        {notes.recent.length > 0 && (
          <ul className={styles.entries}>
            {notes.recent.map((entry) => (
              <li key={entry.id}>
                {editing === entry.id ? (
                  <EntryForm id={`entry-${entry.id}`} initial={{ entry_date: entry.entry_date, body: entry.body, target: key }}
                    busy={update.isPending || remove.isPending} error={update.error ?? remove.error}
                    onSave={(draft) => update.mutate({ id: entry.id, draft })} onCancel={() => setEditing(null)}
                    onDelete={() => remove.mutate(entry.id)} />
                ) : <EntryRow entry={entry} onEdit={() => setEditing(entry.id)} />}
              </li>
            ))}
          </ul>
        )}
        {notes.count > RECENT && (
          <Link className={forms.link} to={`/ustawienia/dziennik?target=${encodeURIComponent(key)}`}>
            {`Wszystkie wpisy (${notes.count}) ›`}
          </Link>
        )}
      </div>
    </section>
  );
}
