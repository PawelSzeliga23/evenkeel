import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { formatPercent } from "../../format";
import ui from "../../ui/ui.module.css";
import { RECALC_POLL_MS } from "../dashboard/model";
import { NO_TAGS, NO_VALUE, TAGS_PATH } from "./model";
import styles from "./Tags.module.css";

/** Analiza's card: the three largest tags with their shares; an invitation while there are none. */
export function TagsCard() {
  const [accountIds, , ready] = useAccountSelection();
  const report = useQuery({
    queryKey: keys.tagAnalytics(accountIds, "all"), queryFn: () => api.tagAnalytics(accountIds, "all"), enabled: ready,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
  });
  const tags = useQuery({ queryKey: keys.tags, queryFn: api.tags });
  const data = report.data;
  if (!data || (data.tags.length === 0 && !tags.data)) return null;
  const top = data.tags.slice(0, 3);
  return (
    <section className={ui.section} aria-labelledby="tags-title">
      <div className={ui.sectionHead}>
        <h2 id="tags-title" className={ui.sectionTitle}>Tagi</h2>
        {top.length > 0 && <Link className={ui.sectionMore} to={TAGS_PATH}>Tagi</Link>}
      </div>
      {top.length === 0 ? <p className={styles.note}>{tags.data!.length === 0 ? NO_TAGS : NO_VALUE}</p> : (
        <ul className={styles.cardList}>
          {top.map((tag) => (
            <li key={tag.id}>
              <i className={styles.dot} style={{ background: tag.color }} aria-hidden="true" />
              <span>{tag.name}</span>
              <span className="num">{formatPercent(tag.share_pct, { sign: false })}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
