import { useEffect, useState } from "react";

/**
 * True once `loading` has been true for longer than `delayMs`. Render's free
 * tier sleeps after inactivity and can take 30-50s to wake on the first
 * request after that - without this, a cold start just looks like a hung
 * "Loading…" state with no explanation. Any loading UI should use this to
 * switch to a "waking up the server" message instead of leaving the user
 * guessing.
 */
export function useSlowLoading(loading: boolean, delayMs = 4000): boolean {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!loading) {
      setSlow(false);
      return;
    }
    const timer = setTimeout(() => setSlow(true), delayMs);
    return () => clearTimeout(timer);
  }, [loading, delayMs]);

  return slow;
}

export const WAKING_UP_MESSAGE =
  "Waking up the server — this can take up to 30–50s if it has been idle. Hang tight…";
