import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../../api/endpoints";
import { errorMessage } from "../../api/messages";
import { keys } from "../../api/queryKeys";
import type { Tag } from "../../api/types";
import { TAG_PALETTE, tagColor } from "../../tags/model";
import { TagChip } from "../../tags/TagChip";
import tagStyles from "../../tags/Tags.module.css";
import { BackLink } from "../../ui/BackLink";
import { Confirm, FormError } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { NO_TAGS, holdingsLabel } from "../tags/model";
import styles from "./Settings.module.css";

/** „Zniknie z {n} walorów” in the genitive: z 1 waloru, z 4 walorów. */
const fromHoldings = (n: number) => `${n} ${n === 1 ? "waloru" : "walorów"}`;

function TagItem({ tag }: { tag: Tag }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [name, setName] = useState(tag.name);
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.portfolio });
  const update = useMutation({
    mutationFn: (body: { name?: string; color?: string }) => api.updateTag(tag.id, body),
    onSuccess: async (_, body) => { if (body.name !== undefined) setEditing(false); await refresh(); },
  });
  const remove = useMutation({ mutationFn: () => api.deleteTag(tag.id), onSuccess: refresh });
  const failed = update.isError ? update.error : remove.isError ? remove.error : null;

  function save(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) update.mutate({ name: name.trim() });
  }

  return (
    <li className={styles.tagItem} aria-label={tag.name}>
      <div className={styles.tagHead}>
        <TagChip tag={tag} />
        <span className="dim">{holdingsLabel(tag.links)}</span>
        <span className={styles.tagActions}>
          <button type="button" className={ui.secondary} aria-label={`Zmień nazwę ${tag.name}`} aria-expanded={editing}
            onClick={() => { setName(tag.name); setEditing(!editing); }}>Zmień</button>
          <button type="button" className={ui.secondary} aria-label={`Usuń ${tag.name}`} onClick={() => setDeleting(true)}>
            Usuń
          </button>
        </span>
      </div>
      {editing && (
        <form className={styles.tagEdit} onSubmit={save}>
          <div className={forms.field}>
            <label htmlFor={`tag-name-${tag.id}`}>Nazwa tagu</label>
            <div className={styles.tagName}>
              <input id={`tag-name-${tag.id}`} value={name} maxLength={30} onChange={(e) => setName(e.target.value)} />
              <button type="submit" className={ui.secondary} disabled={update.isPending}>Zapisz</button>
            </div>
          </div>
          <div className={tagStyles.chips} role="group" aria-label="Kolor tagu">
            {TAG_PALETTE.map((color) => (
              <button key={color} type="button" className={styles.swatch} aria-label={`Kolor ${color}`}
                aria-pressed={tag.color === color} style={{ background: tagColor(color) }} onClick={() => update.mutate({ color })} />
            ))}
          </div>
        </form>
      )}
      {deleting && (
        <Confirm question={`Usunąć tag ${tag.name}? Zniknie z ${fromHoldings(tag.links)}.`} confirmLabel="Usuń"
          busy={remove.isPending} onConfirm={() => remove.mutate()} onCancel={() => setDeleting(false)} />
      )}
      <FormError message={failed ? errorMessage(failed) : null} />
    </li>
  );
}

/** Więcej → Tagi (plan 7f-1): rename, recolour and delete the owner's tags. */
export function TagsSettingsScreen() {
  const tags = useQuery({ queryKey: keys.tags, queryFn: api.tags });
  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      <h1 className={ui.pageTitle}>Tagi</h1>
      {tags.isPending ? <Skeleton rows={3} />
        : tags.isError ? <ErrorState error={tags.error} onRetry={() => void tags.refetch()} />
        : tags.data.length === 0 ? <EmptyState title={NO_TAGS} />
        : <ul className={styles.tagList}>{tags.data.map((tag) => <TagItem key={tag.id} tag={tag} />)}</ul>}
    </div>
  );
}
