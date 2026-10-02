import type { CatalogGroup } from "../../api/types";
import { Field } from "../../ui/forms";
import { EDO } from "./model";

/** An instrument from the catalog (in its groups), or EDO bonds when `bonds`. */
export function TargetSelect({ id, label, catalog, value, onChange, bonds = false, groups, error }: {
  id: string; label: string; catalog: CatalogGroup[]; value: string; onChange: (value: string) => void;
  bonds?: boolean; groups?: string[]; error?: string;
}) {
  const shown = groups ? catalog.filter((group) => groups.includes(group.group)) : catalog;
  const missing = value !== "" && value !== EDO && !shown.some((group) => group.items.some((item) => String(item.id) === value));
  return (
    <Field id={id} label={label} error={error}>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)} aria-invalid={Boolean(error)}>
        {value === "" && <option value="">Wybierz…</option>}
        {missing && <option value={value}>Instrument niedostępny (id {value})</option>}
        {bonds && <option value={EDO}>Obligacje EDO</option>}
        {shown.map((group) => (
          <optgroup key={group.group} label={group.group}>
            {group.items.map((item) => (
              <option key={`${group.group}-${item.id}`} value={String(item.id)}>{item.name} ({item.ticker})</option>
            ))}
          </optgroup>
        ))}
      </select>
    </Field>
  );
}
