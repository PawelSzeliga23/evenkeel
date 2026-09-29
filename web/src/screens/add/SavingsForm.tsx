import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api } from "../../api/endpoints";
import type { Account, Capitalization, SavingsAccountCreate } from "../../api/types";
import { isPositive, parseAmount, todayIso } from "../../format";
import { AMOUNT_HINT, Field, FormError, formErrors, useInvalidateAfterSave, type FormErrors } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { Segmented } from "../../ui/Segmented";
import ui from "../../ui/ui.module.css";

const WRAPPERS: { value: Account["wrapper"]; label: string }[] = [
  { value: "regular", label: "Zwykłe" }, { value: "ike", label: "IKE" }, { value: "ikze", label: "IKZE" },
];
const CAPITALIZATIONS: { value: Capitalization; label: string }[] = [
  { value: "daily", label: "Dzienna" }, { value: "monthly", label: "Miesięczna" }, { value: "quarterly", label: "Kwartalna" },
];

export function SavingsForm() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [wrapper, setWrapper] = useState<Account["wrapper"]>("regular");
  const [rate, setRate] = useState("");
  const [rateFrom, setRateFrom] = useState(todayIso());
  const [capitalization, setCapitalization] = useState<Capitalization>("monthly");
  const [amount, setAmount] = useState("");
  const [depositDate, setDepositDate] = useState(todayIso());
  const [errors, setErrors] = useState<FormErrors>({ fields: {}, general: null });
  const invalidate = useInvalidateAfterSave();

  const save = useMutation({
    mutationFn: (body: SavingsAccountCreate) => api.createSavingsAccount(body),
    onSuccess: async () => {
      await invalidate();
      navigate("/pozycje");
    },
    onError: (error) => setErrors(formErrors(error, { date_in_future: "date" })),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const annualRate = parseAmount(rate, 4);
    const deposit = parseAmount(amount);
    const fields: Record<string, string> = {};
    if (!name.trim()) fields.name = "Podaj nazwę konta.";
    if (annualRate === null) fields.annual_rate = "Podaj oprocentowanie, np. 5,35.";
    if (deposit === null || !isPositive(deposit)) fields.amount = AMOUNT_HINT;
    setErrors({ fields, general: null });
    if (Object.keys(fields).length > 0 || annualRate === null || deposit === null) return;
    save.mutate({
      name: name.trim(), wrapper, capitalization, annual_rate: annualRate, rate_valid_from: rateFrom,
      first_deposit: { date: depositDate, amount: deposit, note: "" },
    });
  }

  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Konto oszczędnościowe</h1>
      <form className={forms.form} onSubmit={submit} noValidate>
        <Field id="savings-name" label="Nazwa konta" error={errors.fields.name}>
          <input id="savings-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100}
            aria-invalid={Boolean(errors.fields.name)} />
        </Field>
        <Segmented label="Rodzaj konta" options={WRAPPERS} value={wrapper} onChange={setWrapper} />
        <div className={forms.row}>
          <Field id="savings-rate" label="Oprocentowanie roczne (%)" error={errors.fields.annual_rate}>
            <input id="savings-rate" inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)}
              aria-invalid={Boolean(errors.fields.annual_rate)} />
          </Field>
          <Field id="savings-rate-from" label="Obowiązuje od" error={errors.fields.rate_valid_from}>
            <input id="savings-rate-from" type="date" value={rateFrom} onChange={(e) => setRateFrom(e.target.value)} />
          </Field>
        </div>
        <Segmented label="Kapitalizacja odsetek" options={CAPITALIZATIONS} value={capitalization} onChange={setCapitalization} />
        <div className={forms.row}>
          <Field id="savings-amount" label="Pierwsza wpłata" error={errors.fields.amount}>
            <input id="savings-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)}
              aria-invalid={Boolean(errors.fields.amount)} />
          </Field>
          <Field id="savings-date" label="Data wpłaty" error={errors.fields.date}>
            <input id="savings-date" type="date" value={depositDate} max={todayIso()} onChange={(e) => setDepositDate(e.target.value)} />
          </Field>
        </div>
        <p className="dim">Odsetki narastają codziennie i są dopisywane przy kapitalizacji, po potrąceniu 19{" "}% podatku (na IKE i IKZE bez podatku).</p>
        <FormError message={errors.general} />
        <button type="submit" className={ui.primaryButton} disabled={save.isPending}>Załóż konto</button>
      </form>
    </div>
  );
}
