import { MONTHS_SHORT, WEEKDAYS_FULL } from "./format";
import type { DayStat } from "./types";

/** A date range within a single calendar month (matches the mockup's model). */
export interface Range {
  year: number;
  month0: number; // 0..11
  start: number;
  end: number;
}

export const rangeLo = (r: Range) => Math.min(r.start, r.end);
export const rangeHi = (r: Range) => Math.max(r.start, r.end);

export function daysInRange(r: Range | null): number[] {
  if (!r) return [];
  const out: number[] = [];
  for (let d = rangeLo(r); d <= rangeHi(r); d++) out.push(d);
  return out;
}

export function fmtRange(r: Range | null): string {
  if (!r) return "";
  const m = MONTHS_SHORT[r.month0];
  const s = rangeLo(r), e = rangeHi(r);
  return s === e ? `${s} ${m}` : `${s}–${e} ${m}`;
}

/** If a range spans exactly 7 days, label them with weekday names. */
export function weekdayLabelsForRange(r: Range | null): string[] | null {
  if (!r) return null;
  const days = daysInRange(r);
  if (days.length !== 7) return null;
  return days.map((d) => {
    const dow = new Date(r.year, r.month0, d).getDay(); // 0=Sun..6=Sat
    return WEEKDAYS_FULL[dow === 0 ? 6 : dow - 1];
  });
}

export interface RangeStats {
  total: number[];
  look: number[];
  labels: string[];
}

export function getRangeStats(
  r: Range | null,
  daily: Record<string, DayStat> | undefined,
): RangeStats {
  if (!r || !daily) return { total: [], look: [], labels: [] };
  const days = daysInRange(r).filter((d) => daily[String(d)]);
  return {
    total: days.map((d) => daily[String(d)].total),
    look: days.map((d) => daily[String(d)].looking),
    labels: days.map(String),
  };
}

/**
 * Approximate "lookers who stayed at least `secs` seconds" by scaling the daily
 * looking count down. HONEST NOTE: this is an estimate, not a real measurement —
 * we currently store engaged count + total attention, not a per-second dwell
 * histogram. The "+2s" baseline (secs<=2) IS real (that's how `engaged` is
 * defined). Anything above needs the edge to emit dwell-time buckets; until then
 * this slider is approximate. See ROADMAP.
 */
export function filterLook(arr: (number | null)[], secs: number): (number | null)[] {
  if (!secs || secs <= 2) return arr.slice();
  const scale = Math.pow(Math.max(0.02, (16 - secs) / 14), 2);
  return arr.map((v) => (v === null ? null : Math.max(0, Math.round(v * scale))));
}
