// Locale-aware formatting + the shared month/weekday name tables (Spanish),
// matching Hector's mockup exactly.

export const MONTHS = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

export const MONTHS_SHORT = [
  "ene", "feb", "mar", "abr", "may", "jun",
  "jul", "ago", "sep", "oct", "nov", "dic",
];

export const WEEKDAYS_FULL = [
  "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo",
];

// Single-letter weekday headers (Mon..Sun), as used in both calendars.
export const WEEKDAY_LETTERS = ["L", "M", "X", "J", "V", "S", "D"];

export const fmtInt = (n: number): string => n.toLocaleString("es-ES");

/** Traffic-light colour for a daily total — same thresholds as the mockup. */
export function trafficColor(total: number): { bg: string; fg: string } {
  if (total >= 200) return { bg: "#4CAF72", fg: "#fff" };
  if (total >= 140) return { bg: "#FF8C42", fg: "#fff" };
  return { bg: "#E8394A", fg: "#fff" };
}

/** Monday-based offset (0..6) of the 1st of a month, for calendar grids. */
export function firstWeekdayOffset(year: number, monthIndex0: number): number {
  const dow = new Date(year, monthIndex0, 1).getDay(); // 0=Sun..6=Sat
  return dow === 0 ? 6 : dow - 1;
}

export function daysInMonth(year: number, monthIndex0: number): number {
  return new Date(year, monthIndex0 + 1, 0).getDate();
}

/** Human "hace X" relative time from an ISO timestamp (Spanish, compact). */
export function timeAgo(iso: string | null): string {
  if (!iso) return "nunca";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const s = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (s < 60) return "hace un momento";
  const m = Math.round(s / 60);
  if (m < 60) return `hace ${m} min`;
  const h = Math.round(m / 60);
  if (h < 24) return `hace ${h} h`;
  const d = Math.round(h / 24);
  return `hace ${d} d`;
}

/** Two-letter initials for the avatar bubble, e.g. "Joyería Martínez" -> "JM". */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "··";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
