import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { ApiError } from "../../api/client";
import { api } from "../../api/endpoints";
import { errorMessage } from "../../api/messages";
import { keys } from "../../api/queryKeys";
import type { ReviewListItem } from "../../api/types";
import { formatRefreshed, todayIso } from "../../format";
import { AccountSelect } from "../../ui/AccountPicker";
import { BackLink } from "../../ui/BackLink";
import { FormError } from "../../ui/forms";
import { ListRow } from "../../ui/ListRow";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import styles from "./Review.module.css";

export const SECTION_COUNT = 9;
const COPY_FAILED = "Nie udało się skopiować — użyj „Pobierz plik”.";

function ReviewIcon() {
  return (
    <svg className={styles.lead} viewBox="0 0 18 18" aria-hidden="true">
      <path d="M4 2.5h7l3 3v10H4zM6.5 8h5M6.5 11h5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

export function ReviewRow({ review }: { review: ReviewListItem }) {
  return (
    <ListRow to={`/analiza/przeglad/${review.id}`} lead={<ReviewIcon />} title={formatRefreshed(review.created_at)}
      subtitle={review.account_label} value={<small className="dim">{review.sections}/{SECTION_COUNT} sekcji</small>} />
  );
}

/** Prepare the package for claude.ai, paste Claude's answer back, and the saved reviews. */
export function ReviewScreen() {
  const [accountIds, setAccountIds] = useAccountSelection();
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const reviews = useQuery({ queryKey: keys.reviews, queryFn: api.reviews });
  const [status, setStatus] = useState<string | null>(null);
  const [pasted, setPasted] = useState("");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: () => api.saveReview(pasted, accountIds),
    onSuccess: async (review) => {
      await queryClient.invalidateQueries({ queryKey: keys.reviews });
      navigate(`/analiza/przeglad/${review.id}`);
    },
  });

  async function download() {
    try {
      const text = await api.reviewPackage(accountIds);
      const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `evenkeel-przeglad-${todayIso()}.md`;
      link.click();
      URL.revokeObjectURL(url);
      setStatus("Pobrano plik.");
    } catch (error) {
      setStatus(errorMessage(error));
    }
  }

  async function copy() {
    let text: string;
    try {
      text = await api.reviewPackage(accountIds);
    } catch (error) {
      setStatus(errorMessage(error));
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      setStatus("Skopiowano.");
    } catch (error) {
      setStatus(error instanceof ApiError ? errorMessage(error) : COPY_FAILED);
    }
  }

  return (
    <div className={ui.page}>
      <BackLink to="/analiza" label="Analiza" />
      <h1 className={ui.pageTitle}>Przegląd portfela</h1>
      {accounts.data && <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} />}
      <div className={styles.steps}>
        <section className={styles.step} aria-labelledby="step-1">
          <h2 id="step-1">1. Przygotuj pakiet dla Claude</h2>
          <ol>
            <li>Pobierz plik albo skopiuj jego treść.</li>
            <li>W claude.ai włącz wyszukiwanie w sieci, potem załącz plik albo wklej treść.</li>
            <li>Claude odpowie jednym blokiem Markdown — skopiuj go przyciskiem Copy.</li>
          </ol>
          <div className={styles.actions}>
            <button type="button" className={ui.primaryButton} onClick={() => void download()}>Pobierz plik</button>
            <button type="button" className={ui.secondary} onClick={() => void copy()}>Kopiuj do schowka</button>
          </div>
          {status && <p className={styles.status} role="status">{status}</p>}
        </section>
        <section className={styles.step} aria-labelledby="step-2">
          <h2 id="step-2">2. Zapisz odpowiedź</h2>
          <label htmlFor="review-paste" className={styles.note}>Wklej odpowiedź Claude</label>
          <textarea id="review-paste" className={styles.paste} value={pasted} onChange={(e) => setPasted(e.target.value)} />
          <FormError message={save.isError ? errorMessage(save.error) : null} />
          <div className={styles.actions}>
            <button type="button" className={ui.primaryButton} disabled={!pasted.trim() || save.isPending}
              onClick={() => save.mutate()}>Zapisz przegląd</button>
          </div>
        </section>
      </div>
      <section className={ui.section} aria-labelledby="saved-title">
        <h2 id="saved-title" className={ui.sectionTitle}>Zapisane przeglądy</h2>
        {reviews.isPending ? <Skeleton rows={2} />
          : reviews.isError ? <ErrorState error={reviews.error} onRetry={() => void reviews.refetch()} />
          : reviews.data.length === 0 ? <p className={styles.note}>Jeszcze nie ma przeglądu.</p>
          : <div>{reviews.data.map((review) => <ReviewRow key={review.id} review={review} />)}</div>}
      </section>
    </div>
  );
}
