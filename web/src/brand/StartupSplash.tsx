import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { useSession } from "../auth/session";
import { firstBars, nextBars, type SplashBar } from "./bars";
import { Wordmark } from "./Logo";
import styles from "./splash.module.css";

const SUMMARY = ["portfolio", "summary"];
const SLOT = 16; // px between bar starts
const TOP = 46; // px height of the newest bar
const STEP_MS = 1400;
const LEAVE_MS = 950; // a leaving bar is removed once it has sunk under the base

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** True once any portfolio summary query has an answer (data or an error). */
function useSummarySettled(): boolean {
  const cache = useQueryClient().getQueryCache();
  const subscribe = useCallback((notify: () => void) => cache.subscribe(notify), [cache]);
  return useSyncExternalStore(subscribe, () => cache.findAll({ queryKey: SUMMARY }).some((q) => q.state.status !== "pending"));
}

function Bars({ still }: { still: boolean }) {
  const [bars, setBars] = useState<SplashBar[]>(() => firstBars());
  useEffect(() => {
    if (still) return;
    const timer = setInterval(() => setBars((current) => nextBars(current)), STEP_MS);
    return () => clearInterval(timer);
  }, [still]);
  const leaving = bars.some((bar) => bar.leaving);
  useEffect(() => {
    if (!leaving) return;
    const timer = setTimeout(() => setBars((current) => current.filter((bar) => !bar.leaving)), LEAVE_MS);
    return () => clearTimeout(timer);
  }, [leaving]);
  const visible = bars.filter((bar) => !bar.leaving);
  return (
    <div className={styles.bars} aria-hidden="true">
      {bars.map((bar) => {
        const index = visible.indexOf(bar);
        return (
          <span key={bar.id} data-splash-bar="" className={bar.leaving ? `${styles.bar} ${styles.gone}` : styles.bar}
            style={{ left: bar.leaving ? -SLOT : index * SLOT, height: `${(bar.value * TOP).toFixed(2)}px`,
              opacity: bar.leaving ? 1 : 0.55 + 0.15 * index }} />
        );
      })}
    </div>
  );
}

/** The animated Evenkeel screen shown once at start-up, until the first screen has something to show. */
export function StartupSplash({ minMs = 3000 }: { minMs?: number }) {
  const { state } = useSession();
  const [startPath] = useState(() => window.location.pathname);
  const [still] = useState(prefersReducedMotion);
  const [minDone, setMinDone] = useState(false);
  const [phase, setPhase] = useState<"loading" | "leaving" | "gone">("loading");
  const summarySettled = useSummarySettled();

  useEffect(() => {
    const timer = setTimeout(() => setMinDone(true), minMs);
    return () => clearTimeout(timer);
  }, [minMs]);

  const needsSummary = state.status === "signedIn" && startPath === "/";
  const ready = minDone && state.status !== "loading" && (!needsSummary || summarySettled);

  useEffect(() => {
    if (ready && phase === "loading") setPhase("leaving");
  }, [ready, phase]);
  useEffect(() => {
    if (phase !== "leaving") return;
    const timer = setTimeout(() => setPhase("gone"), still ? 500 : 800);
    return () => clearTimeout(timer);
  }, [phase, still]);

  if (phase === "gone") return null;
  return (
    <div role="status" aria-label="Wczytuję Evenkeel" aria-busy={phase === "loading"} data-phase={phase}
      data-motion={still ? "reduced" : "full"} className={phase === "leaving" ? `${styles.splash} ${styles.leaving}` : styles.splash}>
      <div className={styles.stack}>
        <div className={styles.mark}>
          <Bars still={still} />
          <span className={styles.base} />
        </div>
        <Wordmark className={styles.word} />
      </div>
    </div>
  );
}
