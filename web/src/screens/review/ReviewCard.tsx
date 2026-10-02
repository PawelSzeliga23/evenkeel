import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { formatRefreshed } from "../../format";
import ui from "../../ui/ui.module.css";
import styles from "./Review.module.css";

/** On Analiza: when the last review was made, and the way to the review screen; nothing while unreadable. */
export function ReviewCard() {
  const reviews = useQuery({ queryKey: keys.reviews, queryFn: api.reviews });
  if (!reviews.data) return null;
  const latest = reviews.data[0];
  return (
    <section className={ui.section} aria-labelledby="review-title">
      <div className={ui.sectionHead}>
        <h2 id="review-title" className={ui.sectionTitle}>Przegląd AI</h2>
        <Link className={ui.sectionMore} to="/analiza/przeglad">Przegląd portfela</Link>
      </div>
      <p className={styles.note}>
        {latest ? `Ostatni przegląd: ${formatRefreshed(latest.created_at)}` : "Jeszcze nie ma przeglądu."}
      </p>
    </section>
  );
}
