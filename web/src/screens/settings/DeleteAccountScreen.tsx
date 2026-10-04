import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { errorMessage } from "../../api/messages";
import { api } from "../../api/endpoints";
import { useSession } from "../../auth/session";
import { BackLink } from "../../ui/BackLink";
import { Field, FormError } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import ui from "../../ui/ui.module.css";
import { saveBackup } from "./BackupScreen";

export const DELETE_PHRASE = "USUŃ KONTO";

/** Ustawienia → Profil → Usuń konto (plan 8d): the account and all its data, after the password and the phrase. */
export function DeleteAccountScreen() {
  const { accountDeleted } = useSession();
  const [password, setPassword] = useState("");
  const [phrase, setPhrase] = useState("");
  const download = useMutation({ mutationFn: api.backup, onSuccess: saveBackup });
  const remove = useMutation({ mutationFn: () => api.deleteUser(password, phrase), onSuccess: accountDeleted });
  const ready = password !== "" && phrase.trim() === DELETE_PHRASE;

  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia/profil" label="Profil" />
      <h1 className={ui.pageTitle}>Usuń konto</h1>
      <section className={ui.section} aria-label="Kopia przed usunięciem">
        <p>
          Usunięcie skasuje Twoje konto i wszystkie dane: konta, operacje, obligacje, oszczędności, tagi, notatki,
          scenariusze i przeglądy. Tego nie da się cofnąć.
        </p>
        <button type="button" className={ui.secondary} disabled={download.isPending} onClick={() => download.mutate()}>
          {download.isPending ? "Przygotowuję…" : "Pobierz kopię"}
        </button>
        <FormError message={download.isError ? errorMessage(download.error) : null} />
      </section>
      <form className={`${ui.section} ${forms.form}`} aria-label="Usuń konto" noValidate
        onSubmit={(e) => { e.preventDefault(); if (ready) remove.mutate(); }}>
        <Field id="delete-password" label="Hasło">
          <input id="delete-password" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <Field id="delete-phrase" label={`Wpisz ${DELETE_PHRASE}`}>
          <input id="delete-phrase" autoComplete="off" value={phrase} onChange={(e) => setPhrase(e.target.value)} />
        </Field>
        <FormError message={remove.isError ? errorMessage(remove.error) : null} />
        <button type="submit" className={forms.danger} disabled={!ready || remove.isPending}>
          {remove.isPending ? "Usuwam…" : "Usuń konto"}
        </button>
      </form>
    </div>
  );
}
