import { useEffect } from "react";
import { useLocation } from "react-router";

/** A search hit may point at an option inside a subpage (#id): bring it into view. */
export function useHashScroll(ready = true) {
  const { hash } = useLocation();
  useEffect(() => {
    if (ready && hash) document.getElementById(hash.slice(1))?.scrollIntoView?.({ block: "center" });
  }, [hash, ready]);
}
