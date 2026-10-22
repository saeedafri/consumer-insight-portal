import { myName, send } from "./api";
// Saved views: any screen's full state is its URL, so saving an analysis is keeping its link and a name. Kept in this
// browser and shared with the team through the API (api/team.py); Copy link shares one directly.
export type SavedView = { url: string; name: string; saved: string };
const KEY = "cip_saved_views";

export function savedViews(): SavedView[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; }
}

function store(views: SavedView[]): void {
  try { localStorage.setItem(KEY, JSON.stringify(views.slice(0, 100))); } catch { /* private window: nothing kept */ }
}

export const isSaved = (url: string) => savedViews().some(v => v.url === url);
/** Kept in this browser and shared with the team (api/team.py): the Library lists both. */
export function saveView(url: string, name: string): void {
  store([{ url, name, saved: new Date().toISOString() }, ...savedViews().filter(v => v.url !== url)]);
  const by = myName();
  if (by) void send("POST", "/api/v1/team/views", { url, name, by }).catch(() => { /* kept locally; the team list misses it */ });
}
export const removeView = (url: string) => store(savedViews().filter(v => v.url !== url));
