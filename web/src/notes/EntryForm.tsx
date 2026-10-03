import { useState, type FormEvent } from "react";
import { errorMessage } from "../api/messages";
import type { IsoDate, NoteHolding } from "../api/types";
import { formatDate, todayIso } from "../format";
import { Confirm, Field, FormError } from "../ui/forms";
import forms from "../ui/forms.module.css";
import ui from "../ui/ui.module.css";
import { MAX_ENTRY, PORTFOLIO, choiceLabel } from "./model";
import styles from "./Notes.module.css";

/** `target`: a holding's key or PORTFOLIO. */
export interface EntryDraft { entry_date: IsoDate; body: string; target: string }

/** A journal entry being written or changed. With `choices` it also asks what the entry is about. */
export function EntryForm({ id, initial, choices, targetLabel, busy, error, onSave, onCancel, onDelete }: {
  id: string;
  initial: EntryDraft;
  choices?: NoteHolding[];
  /** How to name `initial.target` when it is not among `choices` (e.g. a series without bonds). */
  targetLabel?: string;
  busy: boolean;
  error: unknown;
  onSave: (draft: EntryDraft) => void;
  onCancel: () => void;
  onDelete?: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const [deleting, setDeleting] = useState(false);
  const today = todayIso();
  const valid = draft.body.trim() !== "" && draft.entry_date !== "" && draft.entry_date <= today;
  const known = !choices || draft.target === PORTFOLIO || choices.some((c) => c.key === draft.target);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid && !busy) onSave({ ...draft, body: draft.body.trim() });
  }

  return (
    <form className={styles.form} onSubmit={submit} aria-label="Wpis" noValidate>
      <Field id={`${id}-date`} label="Data">
        <input id={`${id}-date`} type="date" max={today} value={draft.entry_date}
          onChange={(e) => setDraft({ ...draft, entry_date: e.target.value })} />
      </Field>
      {choices && (
        <Field id={`${id}-target`} label="Dotyczy">
          <select id={`${id}-target`} value={draft.target} onChange={(e) => setDraft({ ...draft, target: e.target.value })}>
            <option value={PORTFOLIO}>Portfel</option>
            {!known && <option value={draft.target}>{targetLabel ?? draft.target}</option>}
            {choices.map((c) => <option key={c.key} value={c.key}>{choiceLabel(c)}</option>)}
          </select>
        </Field>
      )}
      <Field id={`${id}-body`} label="Treść">
        <textarea id={`${id}-body`} className={styles.text} rows={3} maxLength={MAX_ENTRY} value={draft.body}
          onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
      </Field>
      <FormError message={error ? errorMessage(error) : null} />
      <div className={forms.actions}>
        <button type="submit" className={ui.primaryButton} disabled={!valid || busy}>Zapisz</button>
        <button type="button" className={forms.cancel} onClick={onCancel}>Anuluj</button>
        {onDelete && <button type="button" className={forms.danger} onClick={() => setDeleting(true)}>Usuń</button>}
      </div>
      {deleting && onDelete && (
        <Confirm question={`Usunąć wpis z ${formatDate(initial.entry_date)}?`} confirmLabel="Usuń" busy={busy}
          onConfirm={onDelete} onCancel={() => setDeleting(false)} />
      )}
    </form>
  );
}
