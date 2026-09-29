import type { Account } from "../api/types";
import styles from "./ui.module.css";

export function AccountPicker({
  accounts, value, onChange, allLabel = "Cały portfel",
}: { accounts: Account[]; value: number | null; onChange: (id: number | null) => void; allLabel?: string }) {
  return (
    <span className={styles.picker}>
      <select aria-label="Konto" value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">{allLabel}</option>
        {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
      </select>
      <svg viewBox="0 0 12 12" aria-hidden="true">
        <path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </span>
  );
}

export function AccountChips({
  accounts, value, onChange,
}: { accounts: Account[]; value: number | null; onChange: (id: number | null) => void }) {
  return (
    <div className={styles.chips} role="group" aria-label="Filtr kont">
      <button type="button" aria-pressed={value === null} onClick={() => onChange(null)}>Wszystkie</button>
      {accounts.map((account) => (
        <button key={account.id} type="button" aria-pressed={value === account.id} onClick={() => onChange(account.id)}>
          {account.name}
        </button>
      ))}
    </div>
  );
}
