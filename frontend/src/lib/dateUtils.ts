/**
 * YYYY-MM-DD for a Date, in the browser's local timezone.
 *
 * Deliberately not `date.toISOString().slice(0, 10)` - toISOString() always
 * outputs UTC, so for anyone outside UTC+0 this can return the wrong
 * calendar day (e.g. in UTC+5:30, the hours between local midnight and
 * 5:30am are still "yesterday" in UTC). That bug bit both the Diet tab's
 * day navigator (prev/next skipped a day) and meal logging (a late-night/
 * early-morning log could silently land on the wrong day) before every
 * "what date is this" call site was moved onto this shared helper.
 */
export function toDateStr(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function todayStr(): string {
  return toDateStr(new Date());
}

/** `dateStr` must be YYYY-MM-DD. Stays in local time throughout - see toDateStr. */
export function addDays(dateStr: string, delta: number): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const d = new Date(year, month - 1, day);
  d.setDate(d.getDate() + delta);
  return toDateStr(d);
}
