import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { api } from "../../api/endpoints";
import { errorMessage } from "../../api/messages";
import { keys } from "../../api/queryKeys";
import { formatDate } from "../../format";
import { BackLink } from "../../ui/BackLink";
import { Confirm, FormError } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { Markdown } from "./Markdown";
import styles from "./Review.module.css";

const LIST = "/analiza/przeglad";

/** One saved review, rendered like a README. */
export function ReviewView() {
  const id = Number(useParams().reviewId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const review = useQuery({ queryKey: keys.review(id), queryFn: () => api.review(id), enabled: Number.isInteger(id) && id > 0 });
  const remove = useMutation({
    mutationFn: () => api.deleteReview(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.reviews });
      navigate(LIST);
    },
  });

  return (
    <div className={ui.page}>
      <BackLink to={LIST} label="Przegląd portfela" />
      {review.isPending ? <Skeleton rows={6} />
        : review.isError ? <ErrorState error={review.error} onRetry={() => void review.refetch()} />
        : (
          <>
            <div>
              <h1 className={ui.pageTitle}>Przegląd z {formatDate(review.data.created_at)}</h1>
              <p className={styles.note}>{review.data.account_label}</p>
            </div>
            {review.data.sections === 0 && (
              <p className={ui.notice} role="status">Nie rozpoznano sekcji przeglądu. Czy to na pewno odpowiedź na pakiet?</p>
            )}
            <Markdown text={review.data.content} />
            <p className={styles.note}>
              Liczby o portfelu pochodzą z Evenkeel; informacje rynkowe — z wyszukiwania Claude. Sprawdź przed decyzją.
            </p>
            <FormError message={remove.isError ? errorMessage(remove.error) : null} />
            {confirming
              ? <Confirm question="Usunąć ten przegląd?" confirmLabel="Usuń" busy={remove.isPending}
                  onConfirm={() => remove.mutate()} onCancel={() => setConfirming(false)} />
              : <div><button type="button" className={forms.danger} onClick={() => setConfirming(true)}>Usuń przegląd</button></div>}
          </>
        )}
    </div>
  );
}
