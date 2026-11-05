import fs from "node:fs";
import zlib from "node:zlib";
import path from "node:path";

// Build-time only: reads the published pipeline output so the public pages carry the latest real figures.
// Every value falls back to a known constant, so a build with no data folder (e.g. CI) still succeeds.
const DIR = process.env.CIP_PUBLISH_DIR
  ? path.join(process.env.CIP_PUBLISH_DIR, "current")
  : path.resolve(process.cwd(), "../data/published/current");

function readGz<T>(rel: string): T | null {
  try { return JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(DIR, rel))).toString()); } catch { return null; }
}

type Wave = { survey_id: number; wave_date: string; study_type: string; survey_family: string; qualified_n: number | null; prior_survey_id: number | null; modules?: string[] };

const FALLBACK = { waves: 372, responses: 190849, latestDate: "2026-10-26", latestLabel: "Week of October 26, 2026", trackers: 269, annual: 24, adhoc: 79, questions: 66, latestId: 0, priorId: 0 };

export type Facts = typeof FALLBACK;

export function siteFacts(): Facts {
  const w = readGz<Wave[]>("api/v1/waves.json.gz");
  if (!w || !w.length) return FALLBACK;
  const trackers = w.filter((x) => x.study_type === "tracker");
  const latest = trackers.reduce((a, b) => (b.wave_date > a.wave_date ? b : a), trackers[0]);
  const book = readGz<{ questions?: unknown[] }>(`api/v1/waves/${latest.survey_id}/book.json.gz`);
  const label = "Week of " + new Date(latest.wave_date + "T00:00:00Z").toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
  return {
    waves: w.length,
    responses: w.reduce((s, x) => s + (x.qualified_n || 0), 0),
    latestDate: latest.wave_date,
    latestLabel: label,
    trackers: trackers.length,
    annual: w.filter((x) => x.study_type === "annual").length,
    adhoc: w.filter((x) => x.study_type === "adhoc").length,
    questions: book?.questions?.length ?? FALLBACK.questions,
    latestId: latest.survey_id,
    priorId: latest.prior_survey_id ?? 0,
  };
}

// A featured finding the user has cleared for public release: a question id + the answer row to show.
export type Featured = { cat: string; qid: string; row: string };

type Book = { questions?: { id: string; text: string; short?: string; groups: { rows: Record<string, unknown>[] }[] }[] };
function cell(bk: Book | null, qid: string, row: string): { text: string; val: number } | null {
  const q = bk?.questions?.find((q) => q.id === qid);
  if (!q) return null;
  for (const g of q.groups) {
    const r = g.rows.find((r) => String(r.label ?? "").trim() === row);
    if (r && typeof r.Total === "number") return { text: q.short || q.text, val: r.Total };
  }
  return null;
}

// Real figures for the featured questions, computed from the latest wave and its prior wave. Empty when the
// allow-list is empty, so no survey answer is published until a question id is explicitly listed.
export function featuredFindings(featured: Featured[]) {
  const f = siteFacts();
  if (!featured.length || !f.latestId) return [];
  const book = readGz<Book>(`api/v1/waves/${f.latestId}/book.json.gz`);
  const prior = f.priorId ? readGz<Book>(`api/v1/waves/${f.priorId}/book.json.gz`) : null;
  return featured.flatMap((ff) => {
    const now = cell(book, ff.qid, ff.row);
    if (!now) return [];
    const was = cell(prior, ff.qid, ff.row);
    const delta = was ? +(now.val - was.val).toFixed(1) : null;
    return [{ cat: ff.cat, head: now.text, row: ff.row, val: Math.round(now.val), delta }];
  });
}
