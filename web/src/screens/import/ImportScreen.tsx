import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type DragEvent } from "react";
import { Link } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { ImportFile, ImportResult } from "../../api/types";
import { formatDate, pluralPl } from "../../format";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import styles from "./Import.module.css";

const ACCEPT = ".xlsx,.zip";

function period(file: ImportFile): string | null {
  if (!file.report_from || !file.report_to) return null;
  return `${formatDate(file.report_from)} – ${formatDate(file.report_to)}`;
}

function FileCard({ file }: { file: ImportFile }) {
  const id = `import-${file.filename.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
  return (
    <section className={styles.card} aria-labelledby={id}>
      <h2 id={id} className={styles.cardTitle}>{file.filename}</h2>
      <p>{file.new_account ? `Zostanie założone konto: ${file.account_name}` : `Konto: ${file.account_name}`}</p>
      {period(file) && <p className="dim num">{period(file)}</p>}
      <dl className={ui.kv}>
        <dt>Nowe operacje</dt><dd>{file.new_transactions}</dd>
        <dt>Już zaimportowane</dt><dd>{file.duplicate_transactions}</dd>
        <dt>Nierozpoznane</dt><dd>{file.unknown_transactions}</dd>
        {file.reclassified_transactions > 0 && <><dt>Do poprawienia</dt><dd>{file.reclassified_transactions}</dd></>}
        <dt>Partie otwarte</dt><dd>{file.open_lots}</dd>
        <dt>Partie zamknięte</dt><dd>{file.closed_lots}</dd>
      </dl>
      {file.warnings.length > 0 && (
        <ul className={styles.warnings}>
          {file.warnings.map((w, i) => <li key={i} className="flag">{w.message}</li>)}
        </ul>
      )}
    </section>
  );
}

function blocker(result: ImportResult): string | null {
  if (result.errors.length > 0) return "Niektórych plików nie da się odczytać. Wybierz pliki bez nich, żeby zapisać import.";
  if (result.files.length === 0) return "Wśród wybranych plików nie ma eksportu z XTB.";
  if (result.files.every((f) => f.new_transactions === 0 && f.reclassified_transactions === 0 && !f.new_account)) {
    return "Nic nowego do zapisania. Wszystkie operacje są już w aplikacji.";
  }
  return null;
}

export function ImportScreen() {
  const queryClient = useQueryClient();
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const preview = useMutation({ mutationFn: api.previewImport });
  const commit = useMutation({
    mutationFn: api.commitImport,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.portfolio });
      void queryClient.invalidateQueries({ queryKey: keys.accounts });
    },
  });

  function choose(list: FileList | null) {
    const chosen = Array.from(list ?? []);
    if (chosen.length === 0) return;
    setFiles(chosen);
    commit.reset();
    preview.mutate(chosen);
  }

  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files);
  }

  function restart() {
    setFiles([]);
    preview.reset();
    commit.reset();
  }

  if (commit.isSuccess) {
    const added = commit.data.files.reduce((total, f) => total + f.new_transactions, 0);
    const fixed = commit.data.files.reduce((total, f) => total + f.reclassified_transactions, 0);
    return (
      <div className={ui.page}>
        <h1 className={ui.pageTitle}>Import zapisany</h1>
        <p>
          Dodano {added} {pluralPl(added, "nową operację", "nowe operacje", "nowych operacji")}.
          {fixed > 0 && ` Poprawiono ${fixed} ${pluralPl(fixed, "operację zapisaną", "operacje zapisane", "operacji zapisanych")} wcześniej jako nierozpoznane.`}
          {" "}Wycena przelicza się w tle.
        </p>
        <div className={styles.actions}>
          <Link className={ui.primaryButton} to="/">Zobacz pulpit</Link>
          <button type="button" className={ui.secondary} onClick={restart}>Wgraj kolejne pliki</button>
        </div>
      </div>
    );
  }

  const result = preview.data;
  const reason = result ? blocker(result) : null;

  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Wgraj eksport z XTB</h1>
      <p className="dim">
        Wybierz pliki XLSX z historią rachunku albo ZIP z kilkoma plikami. Przed zapisem zobaczysz, co zostanie dodane.
      </p>

      <label
        className={`${styles.drop} ${dragging ? styles.dragging : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={drop}
      >
        <input
          className={styles.input}
          type="file"
          multiple
          accept={ACCEPT}
          aria-label="Wybierz pliki"
          onChange={(e) => { choose(e.target.files); e.target.value = ""; }}
        />
        <span className={ui.secondary}>Wybierz pliki</span>
        <span className="dim">albo przeciągnij je tutaj</span>
      </label>

      {files.length > 0 && (
        <ul className={styles.chosen} aria-label="Wybrane pliki">
          {files.map((f, i) => <li key={`${i}-${f.name}`}>{f.name}</li>)}
        </ul>
      )}

      {preview.isPending && <Skeleton rows={4} />}
      {preview.isError && <ErrorState error={preview.error} onRetry={() => preview.mutate(files)} />}

      {result && (
        <>
          {result.errors.map((e) => <p key={e.filename} className="down">{`${e.filename}: ${e.message}`}</p>)}
          {result.skipped.map((name) => <p key={name} className="dim">{`Pominięto plik ${name}: to nie jest eksport XTB (XLSX).`}</p>)}
          {result.files.map((file) => <FileCard key={`${file.filename}-${file.account_number}`} file={file} />)}
          <div className={styles.commit}>
            {reason && <p className="dim">{reason}</p>}
            {commit.isError && <ErrorState error={commit.error} />}
            <button
              type="button"
              className={ui.primaryButton}
              disabled={reason !== null || commit.isPending}
              aria-busy={commit.isPending}
              onClick={() => commit.mutate(files)}
            >
              Zapisz import
            </button>
          </div>
        </>
      )}
    </div>
  );
}
