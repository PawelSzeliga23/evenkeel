import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { errorMessage } from "../../api/messages";
import { api } from "../../api/endpoints";
import type { BackupSummary } from "../../api/types";
import { formatRefreshed, pluralPl, todayIso } from "../../format";
import { BackLink } from "../../ui/BackLink";
import { Field, FormError } from "../../ui/forms";
import ui from "../../ui/ui.module.css";
import styles from "./Settings.module.css";

export const CONFIRM_WORD = "ZASTĄP";
export const RESTORED_NOTICE = "Wczytano kopię. Przeliczam wycenę…";

/** What the file holds, as „4 konta · 120 operacji · …” (only the kinds it has). */
export function contents(counts: BackupSummary["counts"]): string[] {
  const parts: [number, string, string, string][] = [
    [counts.accounts, "konto", "konta", "kont"],
    [counts.transactions, "operacja", "operacje", "operacji"],
    [counts.bond_holdings, "zakup obligacji", "zakupy obligacji", "zakupów obligacji"],
    [counts.savings_accounts, "konto oszczędnościowe", "konta oszczędnościowe", "kont oszczędnościowych"],
    [counts.tags, "tag", "tagi", "tagów"],
    [counts.notes, "notatka", "notatki", "notatek"],
    [counts.scenarios, "scenariusz", "scenariusze", "scenariuszy"],
    [counts.ai_reviews, "przegląd", "przeglądy", "przeglądów"],
  ];
  return parts.filter(([n]) => n > 0).map(([n, one, few, many]) => `${n} ${pluralPl(n, one, few, many)}`);
}

/** Saves the downloaded backup as a dated file (also from Usuń konto). */
export function saveBackup(text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `evenkeel-kopia-${todayIso()}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Ustawienia → Kopia portfela (plan 8c): download the whole portfolio, or restore a file in place of everything. */
export function BackupScreen() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [, setAccountIds] = useAccountSelection();
  const [file, setFile] = useState<File | null>(null);
  const [word, setWord] = useState("");
  const download = useMutation({ mutationFn: api.backup, onSuccess: saveBackup });
  const check = useMutation({ mutationFn: api.checkBackup });
  const restore = useMutation({
    mutationFn: () => api.restoreBackup(file!, word),
    onSuccess: async () => {
      setAccountIds([]); // the restored accounts have new numbers: back to the whole portfolio
      await queryClient.invalidateQueries();
      navigate("/", { state: { notice: RESTORED_NOTICE } });
    },
  });

  const choose = (chosen: File | null) => {
    setFile(chosen);
    setWord("");
    restore.reset();
    if (chosen) check.mutate(chosen);
    else check.reset();
  };
  const summary = file && check.isSuccess ? check.data : null;

  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      <h1 className={ui.pageTitle}>Kopia portfela</h1>

      <section className={ui.section} aria-labelledby="backup-save">
        <h2 id="backup-save" className={ui.sectionTitle}>Pobierz kopię</h2>
        <p className="dim">
          Cały portfel w jednym pliku: konta, operacje, obligacje, oszczędności, tagi, notatki, scenariusze, przeglądy
          i ustawienia. Bez hasła — trzymaj go jak inne prywatne dokumenty.
        </p>
        <button type="button" className={ui.secondary} disabled={download.isPending} onClick={() => download.mutate()}>
          {download.isPending ? "Przygotowuję…" : "Pobierz kopię"}
        </button>
        <FormError message={download.isError ? errorMessage(download.error) : null} />
      </section>

      <section className={ui.section} aria-labelledby="backup-load">
        <h2 id="backup-load" className={ui.sectionTitle}>Wczytaj kopię</h2>
        <Field id="backup-file" label="Plik kopii" hint="Plik evenkeel-kopia-….json z „Pobierz kopię”.">
          <input id="backup-file" type="file" accept=".json,application/json"
            onChange={(e) => choose(e.target.files?.[0] ?? null)} />
        </Field>
        {check.isPending && <p className="dim" role="status">Sprawdzam plik…</p>}
        <FormError message={check.isError ? errorMessage(check.error) : null} />
        {summary && (
          <div className={styles.backupSummary} role="group" aria-label="Zawartość kopii">
            <p>{`Kopia z ${formatRefreshed(summary.exported_at)} (Evenkeel ${summary.app_version})`}</p>
            <p className="dim">{contents(summary.counts).join(" · ") || "Pusty portfel"}</p>
            <p className={styles.warning}>
              Zastąpi wszystkie Twoje obecne dane. Tego nie da się cofnąć — najpierw pobierz kopię obecnych danych.
            </p>
            <Field id="backup-confirm" label={`Wpisz ${CONFIRM_WORD}`}>
              <input id="backup-confirm" value={word} autoComplete="off" onChange={(e) => setWord(e.target.value)} />
            </Field>
            <button type="button" className={ui.primaryButton}
              disabled={word.trim() !== CONFIRM_WORD || restore.isPending} onClick={() => restore.mutate()}>
              {restore.isPending ? "Wczytuję…" : "Wczytaj"}
            </button>
            <FormError message={restore.isError ? errorMessage(restore.error) : null} />
          </div>
        )}
      </section>
    </div>
  );
}
