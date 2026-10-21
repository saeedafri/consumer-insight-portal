// Every answer's change against last week (and last year), significance-tested: the "what changed" list.
import type { Book, Group, Question, Row } from "./api";
import { isFiller } from "./api";
import { pValue, survivesFdr } from "./stats";

export interface Move { q: Question; g: Group; r: Row; label: string; now: number; prior: number | null; d: number | null;
                        p: number; sig: boolean; ly: number | null; dLy: number | null; pLy: number; sigLy: boolean; routing: boolean }

export function moves(book: Book): Move[] {
  const out: Move[] = [];
  for (const q of book.questions) for (const g of q.groups) for (const r of g.rows) {
    if (isFiller(r.label) || r.Total == null) continue;
    const routing = r.flags.includes("base_changed_prior");
    const d = r.prior == null ? null : r.Total - r.prior;
    const dLy = r.ly == null ? null : r.Total - r.ly;
    const p = !routing && d != null && r.prior_base ? pValue(r.Total, g.base, r.prior!, r.prior_base) : 1;
    const pLy = !r.flags.includes("base_changed_ly") && dLy != null && r.ly_base ? pValue(r.Total, g.base, r.ly!, r.ly_base) : 1;
    out.push({ q, g, r, label: g.label ? `${g.label}: ${r.label}` : r.label, now: r.Total, prior: r.prior, d, routing,
               p, sig: false, ly: r.ly, dLy, pLy, sigLy: false });
  }
  // "significant" = survives Benjamini–Hochberg across every answer of the wave (5 % false-discovery rate)
  survivesFdr(out.map(m => m.p)).forEach((keep, i) => { out[i].sig = keep; });
  survivesFdr(out.map(m => m.pLy)).forEach((keep, i) => { out[i].sigLy = keep; });
  return out;
}

/** Who answered (age, gender, region…) shifts with each week's sample; it is context, not news. */
export const isProfile = (m: Move) => /^demograph/i.test(m.q.section) || /^D[1-9]$/i.test(m.q.id);

export const biggest = (list: Move[], key: "d" | "dLy" = "d") =>
  list.filter(m => (key === "d" ? m.sig : m.sigLy) && !isProfile(m)).sort((a, b) => Math.abs(b[key]!) - Math.abs(a[key]!));
