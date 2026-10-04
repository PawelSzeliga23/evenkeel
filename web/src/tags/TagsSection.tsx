import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type CSSProperties, type KeyboardEvent } from "react";
import { api } from "../api/endpoints";
import { errorMessage } from "../api/messages";
import { keys } from "../api/queryKeys";
import type { TagOn } from "../api/types";
import { FormError } from "../ui/forms";
import { Segmented } from "../ui/Segmented";
import ui from "../ui/ui.module.css";
import { TagChip } from "./TagChip";
import { linkBody, rows, tagColor, type TagLevel, type TagTarget } from "./model";
import styles from "./Tags.module.css";

const EVERYWHERE = "Walor — na wszystkich kontach";
const LEVELS: { value: TagLevel; label: string }[] = [
  { value: "everywhere", label: "Dla waloru" },
  { value: "own", label: "Tylko na tym koncie" },
];

function Level({ name, tags, onRemove }: { name: string; tags: TagOn[]; onRemove: (tag: TagOn) => void }) {
  return (
    <div className={styles.level} role="group" aria-label={name}>
      <span className={styles.levelName}>{name}</span>
      <div className={styles.chips}>
        {tags.length === 0 ? <span className={styles.empty}>—</span>
          : tags.map((tag) => <TagChip key={tag.link_id} tag={tag} own={tag.own} onRemove={() => onRemove(tag)} />)}
      </div>
    </div>
  );
}

/** Sekcja „Tagi” in the position, bond and savings details: the tags on both levels and the panel that adds them. */
export function TagsSection({ tags, target, accountId, accountName }: {
  tags: TagOn[]; target: TagTarget; accountId: number; accountName: string;
}) {
  const savings = "savings" in target;
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [level, setLevel] = useState<TagLevel>("everywhere");
  const [name, setName] = useState("");
  const all = useQuery({ queryKey: keys.tags, queryFn: api.tags, enabled: open });
  const { everywhere, own } = rows(tags);
  const onLevel = savings || level === "everywhere" ? everywhere : own;
  const available = (all.data ?? []).filter((tag) => !onLevel.some((t) => t.id === tag.id));
  const body = linkBody(target, savings ? "everywhere" : level, accountId);

  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.portfolio });
  const link = useMutation({ mutationFn: (tagId: number) => api.linkTag(tagId, body), onSuccess: refresh });
  const create = useMutation({
    mutationFn: async (value: string) => api.linkTag((await api.createTag({ name: value })).id, body),
    onSuccess: () => { setName(""); return refresh(); },
  });
  const remove = useMutation({ mutationFn: (tag: TagOn) => api.unlinkTag(tag.link_id), onSuccess: refresh });
  const failed = [link, create, remove].find((m) => m.isError);

  function onKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const value = name.trim();
    if (!value || create.isPending || link.isPending) return;
    const known = (all.data ?? []).find((tag) => tag.name.toLowerCase() === value.toLowerCase());
    if (known) link.mutate(known.id, { onSuccess: () => setName("") });
    else create.mutate(value);
  }

  return (
    <section className={ui.section} aria-labelledby="section-Tagi">
      <h2 id="section-Tagi" className={ui.sectionTitle}>Tagi</h2>
      {savings ? <Level name="Tagi konta" tags={everywhere} onRemove={(tag) => remove.mutate(tag)} /> : (
        <>
          <Level name={EVERYWHERE} tags={everywhere} onRemove={(tag) => remove.mutate(tag)} />
          <Level name={`Tylko na tym koncie (${accountName})`} tags={own} onRemove={(tag) => remove.mutate(tag)} />
        </>
      )}
      <button type="button" className={styles.add} aria-expanded={open} onClick={() => setOpen(!open)}>+ Dodaj tag</button>
      {open && (
        <div className={styles.panel}>
          {!savings && <Segmented label="Poziom tagu" options={LEVELS} value={level} onChange={setLevel} />}
          <div className={styles.chips} role="group" aria-label="Dostępne tagi">
            {available.map((tag) => (
              <button key={tag.id} type="button" className={styles.pick} disabled={link.isPending}
                style={{ "--tag": tagColor(tag.color) } as CSSProperties} onClick={() => link.mutate(tag.id)}>
                <i className={styles.dot} aria-hidden="true" />{tag.name}
              </button>
            ))}
          </div>
          <input className={styles.newTag} aria-label="Nowy tag" placeholder="Nowy tag…" maxLength={30} value={name}
            onChange={(e) => setName(e.target.value)} onKeyDown={onKey} />
        </div>
      )}
      <FormError message={failed ? errorMessage(failed.error) : null} />
    </section>
  );
}
