// Two-proportion z-test at 95 %: the same rule as the backend's comparisons (docs/Ui-Design-Claude/13).
export function significant(p1: number, n1: number, p2: number, n2: number): boolean {
  return pValue(p1, n1, p2, n2) < 0.05;
}

/** Two-sided p-value of the two-proportion z-test (1 when it cannot be computed). */
export function pValue(p1: number, n1: number, p2: number, n2: number): number {
  if (!n1 || !n2) return 1;
  const a = p1 / 100, b = p2 / 100;
  const pooled = (a * n1 + b * n2) / (n1 + n2);
  const se = Math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2));
  return se > 0 ? erfc(Math.abs(a - b) / se / Math.SQRT2) : 1;
}

/** Complementary error function (Numerical Recipes erfcc, |error| < 1.2e-7). */
function erfc(x: number): number {
  const t = 1 / (1 + 0.5 * x);
  return t * Math.exp(-x * x - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 +
         t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))));
}

/** Benjamini–Hochberg: which of these tests survive a false-discovery rate of q. Testing hundreds of answers
 *  at 95 % would otherwise flag about 5 % of them every week by chance alone. */
export function survivesFdr(ps: number[], q = 0.05): boolean[] {
  const order = ps.map((p, i) => [p, i] as const).sort((a, b) => a[0] - b[0]);
  let cut = -1;
  order.forEach(([p], k) => { if (p <= ((k + 1) / ps.length) * q) cut = k; });
  const keep = new Array(ps.length).fill(false);
  order.forEach(([, i], k) => { keep[i] = k <= cut; });
  return keep;
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
