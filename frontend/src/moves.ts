// Every answer's change against the previous wave (and last year), significance-tested: the one rule every screen
// uses for "significant". The pipeline's verdict (sig_prior / sig_ly in a row's flags) wins when the book has it;
// older books get the same rule here: Benjamini–Hochberg at 5 % over the answers that could be tested.
import type { Book, Group, Question, Row } from "./api";
import { isFiller } from "./api";
import { fdr, pValue, TEST_BASE } from "./stats";

export interface Move { q: Question; g: Group; r: Row; label: string; now: number; prior: number | null; d: number | null;
                        p: number | null; sig: boolean; ly: number | null; dLy: number | null; pLy: number | null; sigLy: boolean;
                        routing: boolean; testable: boolean; testableLy: boolean }

const has = (flags: string, token: string) => new RegExp(`\\b${token}\\b`).test(flags);
const byBook = new WeakMap<Book, Move[]>();
const byRow = new WeakMap<Row, Move>();

export function moves(book: Book): Move[] {
  const known = byBook.get(book);
  if (known) return known;
  const out: Move[] = [];
  let piped = false;
  for (const q of book.questions) for (const g of q.groups) for (const r of g.rows) {
    piped ||= has(r.flags, "sig_prior") || has(r.flags, "sig_ly");
    if (isFiller(r.label) || r.Total == null) continue;
    const routing = r.flags.includes("base_changed_prior");
    const d = r.prior == null ? null : r.Total - r.prior;
    const dLy = r.ly == null ? null : r.Total - r.ly;
    // testable, as the pipeline decides it (etl/serving.py): a prior with the same wording and the same group asked,
    // 30+ people each side. Respondent profiles are tested too; they are only kept out of the headlines (isProfile)
    const testable = d != null && !routing && !r.flags.includes("wording_changed_prior")
      && g.base >= TEST_BASE && (r.prior_base ?? 0) >= TEST_BASE;
    const testableLy = dLy != null && !r.flags.includes("base_changed_ly") && !r.flags.includes("wording_changed_ly")
      && g.base >= TEST_BASE && (r.ly_base ?? 0) >= TEST_BASE;
    out.push({ q, g, r, label: g.label ? `${g.label}: ${r.label}` : r.label, now: r.Total, prior: r.prior, d, routing,
               p: testable ? pValue(r.Total, g.base, r.prior!, r.prior_base!) : null, sig: false, ly: r.ly, dLy,
               pLy: testableLy ? pValue(r.Total, g.base, r.ly!, r.ly_base!) : null, sigLy: false, testable, testableLy });
  }
  if (piped) out.forEach(m => { m.sig = has(m.r.flags, "sig_prior"); m.sigLy = has(m.r.flags, "sig_ly"); });
  else {
    fdr(out.map(m => m.p)).forEach((keep, i) => { out[i].sig = keep; });
    fdr(out.map(m => m.pLy)).forEach((keep, i) => { out[i].sigLy = keep; });
  }
  out.forEach(m => byRow.set(m.r, m));
  byBook.set(book, out);
  return out;
}

/** The verdict for one answer row of a book already read by moves() (useBook does so as it loads). */
export const moveOf = (r: Row) => byRow.get(r);

/** Who answered (age, gender, region…) shifts with each week's sample; it is context, not news. */
export const isProfile = (m: Move) => /^demograph/i.test(m.q.section) || /^D[1-9]$/i.test(m.q.id);

export const biggest = (list: Move[], key: "d" | "dLy" = "d") =>
  list.filter(m => (key === "d" ? m.sig : m.sigLy) && !isProfile(m)).sort((a, b) => Math.abs(b[key]!) - Math.abs(a[key]!));
