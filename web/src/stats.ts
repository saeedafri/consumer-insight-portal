// Two-proportion z-test at 95 %: the same rule as the backend's comparisons (docs/Ui-Design-Claude/13).
export function significant(p1: number, n1: number, p2: number, n2: number): boolean {
  if (!n1 || !n2) return false;
  const a = p1 / 100, b = p2 / 100;
  const pooled = (a * n1 + b * n2) / (n1 + n2);
  const se = Math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2));
  return se > 0 && Math.abs(a - b) / se > 1.96;
}

/** A column against everyone else (Total minus the column), so a big column is not tested against itself. */
export function versusRest(col: number, colBase: number, total: number, totalBase: number): -1 | 0 | 1 {
  const restBase = totalBase - colBase;
  if (restBase <= 0 || colBase <= 0) return 0;
  const rest = (total * totalBase - col * colBase) / restBase;
  if (!significant(col, colBase, rest, restBase)) return 0;
  return col > rest ? 1 : -1;
}

export const SMALL_BASE = 50;
export const pct = (v: number | null | undefined) => (v == null ? "–" : `${v.toFixed(1)}%`);
export const pts = (d: number) => `${d > 0 ? "+" : d < 0 ? "−" : "±"}${Math.abs(d).toFixed(1)} pts`;
export const count = (p: number, base: number) => Math.round((p / 100) * base);
export const fmtDate = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

/** 95 % margin of error, in points, of a percentage p on n respondents. */
export const moe = (p: number, n: number) => (n > 0 ? 1.96 * Math.sqrt((p / 100) * (1 - p / 100) / n) * 100 : 0);
