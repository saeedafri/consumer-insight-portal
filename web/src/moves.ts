// Every answer's change against last week (and last year), significance-tested: the "what changed" list.
import type { Book, Group, Question, Row } from "./api";
import { isFiller } from "./api";
import { significant } from "./stats";

export interface Move { q: Question; g: Group; r: Row; label: string; now: number; prior: number | null; d: number | null;
                        sig: boolean; ly: number | null; dLy: number | null; sigLy: boolean; routing: boolean }

export function moves(book: Book): Move[] {
  const out: Move[] = [];
  for (const q of book.questions) for (const g of q.groups) for (const r of g.rows) {
    if (isFiller(r.label) || r.Total == null) continue;
    const routing = r.flags.includes("base_changed_prior");
    const d = r.prior == null ? null : r.Total - r.prior;
    const dLy = r.ly == null ? null : r.Total - r.ly;
    out.push({ q, g, r, label: g.label ? `${g.label}: ${r.label}` : r.label, now: r.Total, prior: r.prior, d, routing,
               sig: !routing && d != null && !!r.prior_base && significant(r.Total, g.base, r.prior!, r.prior_base),
               ly: r.ly, dLy, sigLy: !r.flags.includes("base_changed_ly") && dLy != null && !!r.ly_base && significant(r.Total, g.base, r.ly!, r.ly_base) });
  }
  return out;
}

/** Who answered (age, gender, region…) shifts with each week's sample; it is context, not news. */
export const isProfile = (m: Move) => /^demograph/i.test(m.q.section) || /^D[1-9]$/i.test(m.q.id);

export const biggest = (list: Move[], key: "d" | "dLy" = "d") =>
  list.filter(m => (key === "d" ? m.sig : m.sigLy) && !isProfile(m)).sort((a, b) => Math.abs(b[key]!) - Math.abs(a[key]!));
