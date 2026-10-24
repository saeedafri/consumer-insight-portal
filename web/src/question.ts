// Reading a question file (api.ts QuestionFile): cells by wave × cut × answer, and the Trends view of one cut.
import type { QuestionFile, Trend } from "./api";

export type Cell = { n: number | null; base: number; pct: number | null };   // n, pct: null under HIDDEN_BASE people
export type Cells = (w: number, c: number, a: number) => Cell | undefined;

/** A lookup over the file's cells, built once per file. */
export function cellsOf(f: QuestionFile): Cells {
  const nc = f.cuts.length, na = f.answers.length, map = new Map<number, Cell>();
  for (let k = 0; k < f.w.length; k++) map.set((f.w[k] * nc + f.c[k]) * na + f.a[k], { n: f.n[k], base: f.b[k], pct: f.n[k] == null ? null : Math.round(1000 * f.n[k]! / f.b[k]) / 10 });
  return (w, c, a) => map.get((w * nc + c) * na + a);
}

export const answerLabel = ([item, , label]: QuestionFile["answers"][number]) => (item && item !== label ? `${item} · ${label}` : label);

/** The Trends shape for one cut value: the waves where that group answered, one series per answer. */
export function toTrend(f: QuestionFile, cell: Cells, dim: string, value: string): Trend {
  const c = f.cuts.findIndex(([d, v]) => d === dim && v === value);
  const asked = c < 0 ? [] : f.waves.map((_, i) => i).filter(i => f.answers.some((_, a) => cell(i, c, a)));
  return {
    qcode: f.qcode, dim, value, versions: f.versions,
    waves: asked.map(i => ({ survey_id: f.waves[i][0], wave_date: f.waves[i][1], version: f.waves[i][2] })),
    series: f.answers.map((ans, a) => ({
      item_label: ans[0], code: ans[1], label: ans[2] || ans[0],
      pct: asked.map(i => cell(i, c, a)?.pct ?? null), base: asked.map(i => cell(i, c, a)?.base ?? null),
    })).filter(s => s.pct.some(v => v != null)),
  };
}
