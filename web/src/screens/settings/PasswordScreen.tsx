import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api } from "../../api/endpoints";
import { BackLink } from "../../ui/BackLink";
import { Field, FormError, formErrors, type FormErrors } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import ui from "../../ui/ui.module.css";

const MIN_PASSWORD = 10;
const MAX_PASSWORD = 128;
export const PASSWORD_CHANGED = "Hasło zmienione. Inne urządzenia zostaną wylogowane.";
const NO_ERRORS: FormErrors = { fields: {}, general: null };

export function PasswordScreen() {
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);

  const save = useMutation({
    mutationFn: () => api.changePassword(current, next),
    onSuccess: () => navigate("/ustawienia", { state: { notice: PASSWORD_CHANGED } }),
    onError: (error) => {
      const found = formErrors(error, { wrong_password: "current_password" });
      if (found.fields.new_password) {
        found.fields.new_password = next.length < MIN_PASSWORD
          ? `Hasło musi mieć co najmniej ${MIN_PASSWORD} znaków.`
          : `Hasło może mieć najwyżej ${MAX_PASSWORD} znaków.`;
      }
      setErrors(found);
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const fields: Record<string, string> = {};
    if (!current) fields.current_password = "Podaj obecne hasło.";
    if (next.length < MIN_PASSWORD) fields.new_password = `Hasło musi mieć co najmniej ${MIN_PASSWORD} znaków.`;
    else if (next.length > MAX_PASSWORD) fields.new_password = `Hasło może mieć najwyżej ${MAX_PASSWORD} znaków.`;
    if (repeat !== next) fields.repeat = "Hasła różnią się.";
    setErrors({ fields, general: null });
    if (Object.keys(fields).length === 0) save.mutate();
  }

  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      <h1 className={ui.pageTitle}>Zmiana hasła</h1>
      <form className={forms.form} onSubmit={submit} noValidate>
        <Field id="password-current" label="Obecne hasło" error={errors.fields.current_password}>
          <input id="password-current" type="password" autoComplete="current-password" value={current}
            onChange={(e) => setCurrent(e.target.value)} aria-invalid={Boolean(errors.fields.current_password)} />
        </Field>
        <Field id="password-new" label="Nowe hasło" error={errors.fields.new_password} hint={`Co najmniej ${MIN_PASSWORD} znaków.`}>
          <input id="password-new" type="password" autoComplete="new-password" value={next}
            onChange={(e) => setNext(e.target.value)} aria-invalid={Boolean(errors.fields.new_password)} />
        </Field>
        <Field id="password-repeat" label="Powtórz nowe hasło" error={errors.fields.repeat}>
          <input id="password-repeat" type="password" autoComplete="new-password" value={repeat}
            onChange={(e) => setRepeat(e.target.value)} aria-invalid={Boolean(errors.fields.repeat)} />
        </Field>
        <FormError message={errors.general} />
        <button type="submit" className={ui.primaryButton} disabled={save.isPending}>Zmień hasło</button>
      </form>
    </div>
  );
}
