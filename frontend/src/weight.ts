// Census-weighted or unweighted figures (etl/weighting.py): one switch for every wave screen, remembered per browser.
// Unweighted is the default: it matches Forsta and the team's Excel files.
import { useSyncExternalStore } from "react";
import type { Book } from "./api";

const KEY = "cip.weighted";
let on = (() => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } })();
const listeners = new Set<() => void>();
export const useWeighted = () => useSyncExternalStore(f => { listeners.add(f); return () => listeners.delete(f); }, () => on);
export function setWeighted(next: boolean) {
  on = next;
  try { localStorage.setItem(KEY, next ? "1" : "0"); } catch { /* private window: this visit only */ }
  listeners.forEach(f => f());
}

/** The book with each figure replaced by its weighted one (row.w), prior week and last year included. A wave with
 *  no profile to weight on has no row.w and stays as it is; its source line keeps saying "unweighted". */
export function weigh(book: Book): Book {
  if (!book.wave.weighting_available) return book;
  for (const q of book.questions) for (const g of q.groups) for (const r of g.rows) {
    if (!r.w) continue;
    Object.assign(r, r.w, { prior: r.w.prior ?? null, ly: r.w.ly ?? null });
  }
  book.wave = { ...book.wave, weighting: book.wave.weighting_available };
  return book;
}
