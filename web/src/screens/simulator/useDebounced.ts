import { useEffect, useState } from "react";

/** `value` once it has stayed the same (by its JSON) for `ms`; the first value at once. */
export function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  const key = JSON.stringify(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` stands for `value`
  }, [key, ms]);
  return settled;
}
