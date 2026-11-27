// The left menu's "New" badges (components/Shell.tsx): a new survey, a teammate's new board, a new week in the
// Consumer Health dataset or a new What's new entry since this browser last opened that menu. What was seen is kept in
// localStorage, per browser, so a private window shows none; the first visit counts everything as seen, so a badge
// only ever means news. Checked by src/news.check.ts.
import { useEffect, useState } from "react";

/** The newest What's new date (screens/WhatsNew.tsx loads only when opened, so the menu cannot read it there).
 *  tests/test_docs.py fails until it equals docs/CHANGELOG.md's newest date. */
export const LATEST_RELEASE = "2026-11-27";

type Markers = Record<string, number | undefined>;   // each menu's newest survey id or time
const KEY = "cip-seen";

/** What this browser has seen after this visit: a menu met for the first time counts as seen, and so does `open`. */
export function remember(markers: Markers, seen: Record<string, number>, open?: string): Record<string, number> {
  const next = { ...seen };
  for (const [menu, marker] of Object.entries(markers))
    if (marker !== undefined && (next[menu] === undefined || menu === open)) next[menu] = marker;
  return next;
}

/** The menus whose newest marker is past what this browser saw. */
export function fresh(markers: Markers, seen: Record<string, number>): Set<string> {
  return new Set(Object.entries(markers).filter(([menu, marker]) => marker !== undefined && seen[menu] !== undefined
    && marker > seen[menu]).map(([menu]) => menu));
}

function read(): Record<string, number> {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "{}"); } catch { return {}; }
}

/** The menus with news, and `see` for one opened without changing screen (a download); `open` is the one on screen. */
export function useNews(markers: Markers, open: string | undefined) {
  const [seen, setSeen] = useState(read);
  const keep = (next: Record<string, number>) => {
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* storage blocked: no badges, nothing breaks */ }
    setSeen(next);
  };
  const known = JSON.stringify(markers);
  useEffect(() => keep(remember(markers, read(), open)), [known, open]);   // eslint-disable-line react-hooks/exhaustive-deps -- markers by value
  return { fresh: fresh(markers, seen), see: (menu: string) => keep(remember({ [menu]: markers[menu] }, read(), menu)) };
}
