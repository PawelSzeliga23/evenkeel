import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { formatDate } from "../../format";
import { BackLink } from "../../ui/BackLink";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import styles from "./Review.module.css";

/** One saved review. */
export function ReviewView() {
  const id = Number(useParams().reviewId);
  const review = useQuery({ queryKey: keys.review(id), queryFn: () => api.review(id), enabled: Number.isInteger(id) && id > 0 });

  return (
    <div className={ui.page}>
      <BackLink to="/analiza/przeglad" label="Przegląd portfela" />
      {review.isPending ? <Skeleton rows={6} />
        : review.isError ? <ErrorState error={review.error} onRetry={() => void review.refetch()} />
        : (
          <>
            <h1 className={ui.pageTitle}>Przegląd z {formatDate(review.data.created_at)}</h1>
            <p className={styles.note}>{review.data.account_label}</p>
            <pre>{review.data.content}</pre>
          </>
        )}
    </div>
  );
}
