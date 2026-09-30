import { useEffect, useId, useRef, useState } from "react";
import type { Account } from "../api/types";
import { ALL_LABEL, selectionLabel, toggleAccount } from "../accounts/selection";
import styles from "./ui.module.css";

/** The account filter: a button describing the choice, opening a panel of checkboxes. */
export function AccountSelect({
  accounts, value, onChange,
}: { accounts: Account[]; value: readonly number[]; onChange: (ids: number[]) => void }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const known = accounts.map((account) => account.id);
  const label = selectionLabel(value, accounts);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      button.current?.focus();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className={styles.select} ref={root}>
      <button
        ref={button} type="button" className={styles.selectButton} aria-label={`Konta: ${label}`}
        aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((was) => !was)}
      >
        <span className={styles.selectLabel}>{label}</span>
        <svg viewBox="0 0 12 12" aria-hidden="true">
          <path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
      {open && (
        <div id={panelId} className={styles.selectPanel} role="group" aria-label="Wybór kont">
          <label className={styles.selectOption}>
            <input type="checkbox" checked={value.length === 0} onChange={() => onChange([])} />
            {ALL_LABEL}
          </label>
          {accounts.map((account) => (
            <label key={account.id} className={styles.selectOption}>
              <input type="checkbox" checked={value.includes(account.id)}
                onChange={() => onChange(toggleAccount(value, account.id, known))} />
              {account.name}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
