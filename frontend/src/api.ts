// The FastAPI contract (api/main.py) and one cached hook per endpoint.
import { keepPreviousData, QueryClient, useQuery } from "@tanstack/react-query";
import { perf } from "./perf";
import { moves } from "./moves";
import { save } from "./csv";
import { useWeighted, weigh } from "./weight";

export type Column = "Total" | "Male" | "Female" | "Gen Z" | "Millennial" | "Gen X" | "Boomer";
export const COLUMNS: Column[] = ["Total", "Male", "Female", "Gen Z", "Millennial", "Gen X", "Boomer"];
/** Banner columns this wave can show: Total, plus every group with at least one respondent (many ad hoc and
 *  archive surveys have no age/gender profile, so their cuts are empty and must not be offered). */
export const present = (n: Partial<Record<Column, number>>): Column[] => COLUMNS.filter(c => c === "Total" || (n[c] ?? 0) > 0);

export const CUT_OF: Record<Column, [string, string]> = {
  Total: ["total", "Total"], Male: ["gender", "Male"], Female: ["gender", "Female"], "Gen Z": ["generation", "GenZ"],
  Millennial: ["generation", "Millennial"], "Gen X": ["generation", "GenX"], Boomer: ["generation", "Boomer"],
};

export interface Wave {
  survey_id: number; title: string; wave_label: string; wave_date: string; survey_family: string;
  study_type: string; qualified_n: number; prior_survey_id: number | null; ly_survey_id: number | null;
  ly_status: "loaded" | "not_loaded" | "none"; modules?: string[]; dashboards?: string[];
  rows_built?: number;   // 0: the wave is registered but has no results yet (some legacy archive loads)
  country?: string; platform?: "forsta" | "qualtrics" | "surveymonkey" | "baidu"; source_ref?: string;
  field_start?: string | null; field_end?: string | null;   // UTC; recorded for Forsta waves only
  events?: string[];     // recurring retail events in the title (config/survey_calendar.yml events), e.g. Prime Day
  population?: string | null; weighting?: string | null;   // who the sample stands for, and how it is weighted ("none")
  weighting_available?: string;   // the book carries Census-weighted figures (row.w): what they are weighted on
  in_field?: boolean;    // still collecting: the figures are partial
  client?: string | null; visibility?: string | null; verified?: boolean;
}

// A module dashboard (api/dashboards.py, config/dashboards.yml): the business team's "this week at a glance"
export interface Metric { label: string; segment: string; pct: number | null; n: number | null; base: number;   // pct, n: null under HIDDEN_BASE people
                          vs_prior: number | null; vs_ly: number | null; ly_pct: number | null; flags: string[] }
export interface WaveRef { survey_id: number | null; wave_no: number; season: number; week_of: string; loaded: boolean }
export interface Dashboard {
  dashboard: string; title: string; wave: WaveRef; prior: WaveRef | null; last_year: WaveRef | null; ly_rule: string;
  tiles: Record<string, Metric | null>; lists: Record<string, Metric[]>; segments: Record<string, Metric[]>;
  takeaways: string[]; small_base: number; data_as_of: string | null;
  tile_labels?: Record<string, string>; highlights?: { list: string; title: string; of: string }[]; prior_label?: string;
}
export interface Row extends Partial<Record<Column, number | null>> {   // null: under HIDDEN_BASE people, no figure
  label: string; code: number | null; prior: number | null; prior_base: number | null;
  ly: number | null; ly_base: number | null; flags: string;
  w?: Partial<Record<Column | "prior" | "ly", number | null>>;   // Census-weighted figures (weight.ts)
}
export interface Group { label: string; base: number; bases: Partial<Record<Column, number>>; rows: Row[] }
export interface Question {
  id: string; text: string; short: string | null; type: "single" | "multi" | "grid_single" | "grid_multi";
  section: string; base_desc: string | null; groups: Group[];
  number: string;   // "Q1", "Q2"…: the question's place in this wave's survey, what people read (bookOf); id stays the survey code
  coded?: "claude" | "frequency";   // an open-ended question coded into themes (etl/open_ends.py)
}
export interface Book { wave: Wave; columns: Column[]; n: Record<Column, number>; questions: Question[] }
export interface Trend {
  qcode: string; dim: string; value: string; waves: { survey_id: number; wave_date: string; version: number }[];
  versions: string[];   // each version's wording, oldest first: one code reused for different questions
  series: { item_label: string; code: number | null; label: string; pct: (number | null)[]; base: (number | null)[] }[];
}
export interface Crosstab {
  survey_id: number; qcode: string; by: [string, string]; weeks: number;
  waves: { survey_id: number; wave_date: string }[]; warnings: string[];
  columns: string[]; rows: (string | number | null)[][];
}
export interface Hit { qcode: string; text: string; type: string; family: string; first: string; last: string; waves: number; survey_id: number; title: string;
  measure_id?: number; measure?: string }   // the harmonised concept: wordings of one measure share it

/** The server asked us to come back in a few seconds (a burst of uncached requests). */
export class Busy extends Error { constructor() { super("The portal is busy; retrying in a few seconds…"); } }

/** One query cache for the app: writes anywhere refresh the lists they change. */
export const queries = new QueryClient({ defaultOptions: { queries: {
  refetchOnWindowFocus: false,
  retry: (count, error) => (error instanceof Busy ? count < 3 : count < 1),   // busy: up to 3 tries, 3 s apart
  retryDelay: (_, error) => (error instanceof Busy ? 3000 : 800),
} } });

/** Not signed in (never was, or the session ended): the home page, whose Sign in leads to /sign-in/ and the provider.
 *  Straight to the provider instead would skip the home page and look like a jump to another site. */
export function signIn(): never {
  location.replace("/");
  throw new Error("Sign in required");
}

/** The answer the page asked for while it was still loading (app/app/layout.tsx), once: a body can be read only once. */
async function takeEarly(url: string): Promise<Response | null> {
  const early = (window as { __early?: Record<string, Promise<Response>> }).__early;
  const asked = early?.[url];
  if (!asked) return null;
  delete early[url];
  return asked.catch(() => null);   // the early ask failed (offline for a moment): ask again normally
}

async function get<T>(url: string): Promise<T> {
  const deregister = perf.registerPendingApi(url);
  const t0 = performance.now();
  let status = 0;
  let serverDur: number | null = null;
  let size: number | null = null;

  try {
    const r = await takeEarly(url) ?? await fetch(url, { credentials: "same-origin" });
    status = r.status;
    const dur = performance.now() - t0;

    const serverTiming = r.headers.get("server-timing");
    if (serverTiming) {
      const match = serverTiming.match(/dur=([\d.]+)/);
      if (match) serverDur = parseFloat(match[1]);
    }
    const contentLength = r.headers.get("content-length");
    if (contentLength) size = parseInt(contentLength, 10);

    perf.logApi({
      url,
      endpoint: url.split("?")[0],
      method: "GET",
      status: r.status,
      durationMs: dur,
      serverDurationMs: serverDur,
      sizeBytes: size,
      source: "network",
    });

    if (r.status === 401) signIn();
    if (r.status === 403 && url !== "/api/v1/me") void queries.invalidateQueries({ queryKey: ["me"] });   // access may have changed: redraw the menu
    if (r.status === 503) throw new Busy();   // admission control: the query client waits and retries
    // the status rides on the error, so a screen can tell "not there" (404) from a failure without reading the wording
    if (!r.ok) throw Object.assign(new Error((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`), { status: r.status });
    return r.json();
  } catch (err) {
    if (status === 0) {
      perf.logApi({
        url,
        endpoint: url.split("?")[0],
        method: "GET",
        status: 0,
        durationMs: performance.now() - t0,
        serverDurationMs: null,
        sizeBytes: null,
        source: "network",
      });
    }
    throw err;
  } finally {
    deregister();
  }
}

const forever = { staleTime: 5 * 60_000, gcTime: 30 * 60_000 };
export const useWaves = () => useQuery({ queryKey: ["waves"], queryFn: () => get<Wave[]>("/api/v1/waves"), ...forever });
/** The weekly US Consumer Survey Insights report of a recent tracker wave, built by the ETL (etl/weekly_report.py) and
 *  read as it is by the Report screen (screens/Report.tsx). Figures are % of respondents, four-week rolling averages. */
export interface ReportRow { label: string; values: (number | null)[]; week_change: number | null; quarter_change: number | null;
  week_significant: boolean; quarter_significant: boolean }
export interface ReportTable { dates: (string | null)[]; rows: ReportRow[]; trend: { dates: (string | null)[]; lines: Record<string, (number | null)[]> } }
export interface AppendixRow { label: string; values: (number | null)[]; week_change: number | null; four_week_change: number | null }
export interface SentimentLine { weekly: (number | null)[]; four_week: (number | null)[]; year_change: number | null }
export interface WeeklyReport {
  survey_id: number; wave_date: string;
  three_points: { section: string; label: string; change: number; from: number; to: number; from_date: string; to_date: string }[];
  sentiment: Record<string, { dates: (string | null)[]; lines: Record<string, SentimentLine> }>;
  appendix: Record<string, { dates: (string | null)[]; four_week: Record<string, AppendixRow[]>; weekly: AppendixRow[] }>;
  tables: (ReportTable & { part: string; name: string; title: string; question: string })[];
  profiles: { title: string; rows: { label: string; shoppers: number; age: number; income_k: number }[] }[];
  methodology: { weeks: { date: string; respondents: number }[]; weekly_margin: number; four_week_margin: number };
  events: { date: string; label: string; kind: "economy" | "retail" }[];
}
export const useReport = (id: number) =>
  useQuery({ queryKey: ["report", id], queryFn: () => get<WeeklyReport>(`/api/v1/waves/${id}/report`), ...forever, enabled: id > 0, retry: false });

/** The waves with a weekly report (etl/weekly_report.py): the left menu shows the link only for them. */
export const useReportWaves = () =>
  useQuery({ queryKey: ["report-waves"], queryFn: () => get<number[]>("/api/v1/reports"), ...forever, retry: false });

/** The Databank's sector tables (etl/sectors.py): one column per wave the sector ran. */
export interface Sector {
  name: string; margin: number;
  waves: { survey_id: number; date: string; respondents: number }[];
  purchase: { label: string; values: (number | null)[] } | null;
  tables: { title: string; question: string; bases: (number | null)[]; rows: { label: string; values: (number | null)[] }[] }[];
}
export const useSectors = () =>
  useQuery({ queryKey: ["sectors"], queryFn: () => get<{ sectors: Sector[] }>("/api/v1/sectors"), ...forever, retry: false });

/** Retailer comparison (etl/retailers.py): the newest weeks, each pooled with the weeks before it; per retailer and week
 *  its reach (% of respondents), buyers, their profile (% per group, null under min_buyers) and sentiment if asked. */
export type Profile = { gender: (number | null)[]; generation: (number | null)[]; income: (number | null)[] };
export interface Retailers {
  weeks: { survey_id: number; date: string; from: string; weeks: number; respondents: number }[];
  groups: Record<keyof Profile, string[]>;
  everyone: Profile[];
  min_buyers: number;
  retailers: { name: string; reach: Record<"any" | "food" | "nonfood", (number | null)[]>; buyers: number[]; profile: (Profile | null)[];
               sentiment: { positive: number; n: number; date: string } | null }[];
}
export const useRetailers = () =>
  useQuery({ queryKey: ["retailers"], queryFn: () => get<Retailers>("/api/v1/retailers"), ...forever, retry: false });

/** Retail events, expected vs actual (etl/expectations.py). */
export interface SpendSide { median: number; answers: number; spenders: number | null; market_billions: number | null }
export interface EventComparison {
  expected: { survey_id: number; date: string }; actual: { survey_id: number; date: string }; same_season: boolean;
  questions: {
    expected_code: string; actual_code: string; expected_text: string; actual_text: string; expected_base: number; actual_base: number;
    rows: { label: string; actual_label: string; expected: number; actual: number; difference: number; significant: boolean }[];
    net: { expected: number; actual: number } | null;
  }[];
  spend: { expected: SpendSide | null; actual: SpendSide | null } | null;
}
export const useExpectations = () =>
  useQuery({ queryKey: ["expectations"], ...forever, retry: false,
    queryFn: () => get<{ us_adults_millions: number; events: { name: string; comparisons: EventComparison[] }[]; outlooks: Outlook[] }>("/api/v1/expectations") });
/** An outlook question asked survey after survey (holiday spending, finances): each survey's answers and net score. */
export interface Outlook { title: string; question: string; dates: string[]; bases: number[]; net: (number | null)[]; rows: { label: string; values: (number | null)[] }[] }

export const useBook = (id: number) => {
  const weighted = useWeighted();
  return useQuery({ queryKey: ["book", id, weighted], queryFn: () => bookOf(id, weighted), ...forever, enabled: id > 0 });
};
/** A wave's book with every answer's significance verdict worked out once (moves.ts), as it loads; weighted on request. */
export const bookOf = (id: number, weighted = false) =>
  get<Book>(`/api/v1/waves/${id}/book`).then(book => {
    book.questions.forEach((q, i) => { q.number = `Q${i + 1}`; });   // survey codes (BD1, LX5RA8OE) are hard to read
    if (weighted) weigh(book); moves(book); return book;
  });
/** One "at a glance" block; Overview starts these with the book, not after it (the codes come from the cached /waves). */
export const dashboardQuery = (code: string | undefined, id: number) =>
  ({ queryKey: ["dashboard", code, id], enabled: !!code && id > 0, ...forever, queryFn: () => get<Dashboard>(`/api/v1/dashboards/${code}/${id}`) });
export const useDashboard = (code: string | undefined, id: number) => useQuery(dashboardQuery(code, id));
/** One question across every wave of its family and every cut, as compact columns (app/data/payloads.question_from):
 *  cell k is waves[w[k]] × cuts[c[k]] × answers[a[k]], n[k] people of b[k]. Compare and Trends slice it on screen. */
export interface QuestionFile {
  qcode: string; waves: [number, string, number][]; versions: string[];   // [survey_id, date, version]; wording per version
  answers: [string, number | null, string][]; cuts: [string, string][];   // [item_label, code, label]; [dim, value]
  w: number[]; c: number[]; a: number[]; n: (number | null)[]; b: number[];   // n: null under HIDDEN_BASE people
}
export const CUT_NAMES: Record<string, string> = { gender: "Gender", age_band: "Age band", generation: "Generation", income_band: "Household income",
                                                   census_region: "Census region", urbanicity: "Urbanicity" };
/** Published per question (a static gzip read); fetched once per question, then every wave pick and cut is local. */
export const useQuestion = (wave: Wave | undefined, q: string) =>
  useQuery({ queryKey: ["question", wave?.survey_family, wave?.study_type, q], enabled: !!q && !!wave, ...forever,
             queryFn: () => get<QuestionFile>(`/api/v1/questions/${[wave!.survey_family, wave!.study_type, q].map(encodeURIComponent).join("/")}`) });
export const useCrosstab = (id: number, q: string, by: [string, string], weeks: number, on: boolean) =>
  useQuery({ queryKey: ["crosstab", id, q, by, weeks], enabled: on && !!q, ...forever,
             queryFn: () => get<Crosstab>(`/api/v1/waves/${id}/crosstab?q=${encodeURIComponent(q)}&by=${by.join(",")}&weeks=${weeks}`) });
export const SEARCH_PAGE = 50;
export const useSearch = (text: string, page = 1) =>
  useQuery({ queryKey: ["search", text, page], enabled: text.trim().length >= 2, ...forever, placeholderData: previous => previous,
             queryFn: () => get<{ results: Hit[]; total: number; understood: { corrected: string[]; expanded: string[]; matched_by: string } }>(
               `/api/v1/search?q=${encodeURIComponent(text.trim())}&limit=${SEARCH_PAGE}&offset=${(page - 1) * SEARCH_PAGE}`) });

/** Rows of a question that make sense to rank: drops "None of these" / "Other – please specify". */
export const isFiller = (label: string) => /^(none of (these|the above)|other\s*[-–(]|prefer not)/i.test(label.trim());

export type LaunchWeek = { date: string; cycle: number; sector: string; topics: string[];
  status: "loaded" | "in_field" | "closed" | "load_failed" | "setting_up" | "planned" | "not_found";
  survey_id: number | null; title: string | null; qualified: number | null; quota: number;
  launched: string | null; closed: string | null; notes: string[];
  quota_cells: QuotaCell[] | null; quota_at: string | null;   // quota left per cell, last read while live
  history: { at: string; state: string; load_state: string; qualified: number | null }[] };
export type QuotaCell = { sheet: string; cell: string; limit: number; complete: number; conditional: boolean };
export type TopicRotation = { topic: string; sectors: string[]; last: string | null; fielded: number; next: string | null; next_sector: string | null };
export type Schedule = { source: string; imported: string; quota: number; plan_ends: string | null; corrected: string[]; topics: TopicRotation[]; weeks: LaunchWeek[] };
/** Refetched every minute: the API rebuilds it from the Forsta register on every poll. */
export const useSchedule = () => useQuery({ queryKey: ["schedule"], queryFn: () => get<Schedule>("/api/v1/schedule"),
                                            staleTime: 60_000, refetchInterval: 60_000 });

/** A write to the portal's own team store (saved views, alerts, audiences) or a question to Ask CIP. */
export async function send<T>(method: "POST" | "DELETE", url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, { method, credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: body == null ? undefined : JSON.stringify(body) });
  if (r.status === 401) signIn();
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`);
  return (r.status === 204 ? null : r.json()) as T;
}

/** The signed-in person's API keys (Account page): never the key itself, which is shown once when made. */
export interface ApiKey { shown: string; name: string; created: string }
export const useKeys = () => useQuery({ queryKey: ["keys"], queryFn: () => get<{ keys: ApiKey[] }>("/api/v1/keys") });

export interface TeamView { view_id: number; name: string; url: string; note: string | null; saved_by: string; created_at: string }
export interface Alert { alert_id: number; name: string; qcode: string; answer_label: string; dim: string; dim_value: string; against: "prior" | "ly";
                         created_by: string; created_at: string; last_fired: number | null }
export interface AudienceDef { cuts: Record<string, string[]>; answers: { qcode: string; qtext: string; item_label: string; option_code: number | null; label: string }[] }
export interface Audience { audience_id: number; name: string; definition: AudienceDef; created_by: string }
export interface AudienceResult { qcode: string; multi: boolean; skipped: string[]; rows: [string, number | null, number, number | null, number | null, number, number, number | null][] }
export interface Distinctive { qcode: string; question: string; answer: string; pct: number; everyone: number; index: number; base: number }
export interface AudienceProfile { size: number; skipped: string[]; over: Distinctive[]; under: Distinctive[] }
/** Ask CIP's answer (api/assistant.py): sentences, the chart that fits, every figure as a table, and other matches. */
export interface AskChart { type: "line" | "bar" | "grouped" | "donut"; categories: string[]; series: { name: string; data: (number | null)[] }[]; unit: string }
export interface Answer { answer: string; no_source: boolean; mode: "figures" | "none"; chart: AskChart | null;
                          table: { head: string[]; rows: (string | number | null)[][]; bases: number[] } | null;
                          sources: { id: string; key: string; survey_id: number; wave_date: string; qcode: string; question: string; family: string; waves: number; link: string }[];
                          suggestions: { qcode: string; text: string; family: string; key: string }[] }
export interface BoardSummary { board_id: number; name: string; created_by: string; created_at: string; items: number }
export interface BoardComment { comment_id: number; author: string; body: string; created_at: string }
export interface BoardItem { item_id: number; title: string; url: string; data_version: string; added_by: string; added_at: string;
                             spec: { name: string; header: string[]; rows: (string | number | null)[][]; notes: string[] }; comments: BoardComment[] }
export interface Board { board_id: number; name: string; created_by: string; created_at: string; current_version: string; items: BoardItem[] }
// Team lists: read once, then refreshed by the writes that change them (invalidateQueries), not on every visit
const team = { staleTime: 5 * 60_000 };
export const useBoards = (enabled = true) => useQuery({ queryKey: ["boards"], queryFn: () => get<BoardSummary[]>("/api/v1/boards"), ...team, enabled });
export const useBoard = (id: number) => useQuery({ queryKey: ["board", id], queryFn: () => get<Board>(`/api/v1/boards/${id}`), ...team });
export const useTeamViews = () => useQuery({ queryKey: ["team-views"], queryFn: () => get<TeamView[]>("/api/v1/team/views"), ...team });
export const useAlerts = () => useQuery({ queryKey: ["alerts"], queryFn: () => get<Alert[]>("/api/v1/alerts"), ...team });
export const useAudiences = () => useQuery({ queryKey: ["audiences"], queryFn: () => get<Audience[]>("/api/v1/audiences"), ...team });

/** The signed-in person (api /me). null before the API serves it: every screen then shows every feature. */
export interface Me { email: string; name: string | null; role: string | null; tier: string | null; client: string | null; features: string[] | "*" | null; permissions?: string[] }
const loadMe = () => get<Me>("/api/v1/me").catch(() => null);
/** Who is signed in and what they may open. Re-read when the tab comes back into view, every 5 minutes, and at once after
 *  any refusal (get), so a menu taken away (a trial ended) disappears without a page refresh; the data itself is
 *  refused by the server at once either way (api/signin.py user, deploy/cip_auth.js). */
export const useMe = () => useQuery({ queryKey: ["me"], queryFn: loadMe, staleTime: 60_000, refetchInterval: 300_000, gcTime: Infinity });
/** A feature (config/access.yml: explorer, crosstab, trends, search, ask, export, boards, audiences, alerts, saved_views…)
 *  is shown unless the session lists features and this one is not among them ("*" = all). */
export const allowed = (me: Me | null | undefined, feature: string) => {
  const list = me?.features;
  return !list || list === "*" || list.includes("*") || list.includes(feature);
};

/** Who is saving, from the session (the API records the signed-in user either way). */
export async function myName(): Promise<string> {
  const me = await queries.fetchQuery({ queryKey: ["me"], queryFn: loadMe, staleTime: Infinity });
  let kept: string | null = null;
  try { kept = localStorage.getItem("cip_name"); } catch { /* private window */ }
  return me?.name || me?.email || kept || "Portal user";
}

/** Methodology text (api /methodology); the Methodology page has a built-in version for when it is not served. */
export type Methodology = { title?: string; updated?: string; sections: { title: string; body: string | string[] }[] };
export const useMethodology = () => useQuery({ queryKey: ["methodology"], staleTime: Infinity, retry: false,
  queryFn: () => get<Methodology | string>("/api/v1/methodology") });

/** Forsta's fieldwork record of every survey (etl/fieldwork.py → GET /api/v1/admin/fieldwork, admins only). */
export interface FieldworkSurvey {
  path: string; survey_id: number | null; title: string | null; wave_date: string | null; state: string | null; hibernated: boolean;
  launched: string | null; closed: string | null; questions: number | null; opened: number | null; partial: number | null;
  terminated: number | null; overquota: number | null; qualified: number | null; incidence: number | null; median_minutes: number | null;
  warnings: Record<string, number>; pages: [string, string, number, number, number, number | null][]; fetched_at: string;
  timeline?: [string, string | null, string][]; terms?: [string | null, string | null][];
  saved_reports?: [string | null, string | null, string | null][]; category?: string | null; can_archive?: string | null;
  tasks?: number; layouts?: number; datasources?: number; conditions?: number | null;
  /** why people left: [status, cause, where in the survey, people, average minutes] (etl/fieldwork.py explain) */
  causes?: [string, string, string, number, number | null][];
  /** finished interviews hour by hour, by Forsta's clock: [hour, qualified, terminated, over quota] */
  hours?: [string, number, number, number][];
  /** quota cells, the busiest first: [quota, cell, limit, completes, turned away over quota] */
  quota_cells?: [string, string, number | null, number | null, number | null][];
}
export interface FieldworkRecord {
  surveys: FieldworkSurvey[];
  archive: { path: string; name: string | null; archived_at: string | null; delete_at: string | null; held: boolean }[];
  retention?: { server_delete_days?: number | null; archive_days?: number | null; company?: number }[];
  not_loaded?: { path: string; title: string | null; state: string | null }[];
  planned?: { kind: string; items: unknown[] }[];
  collected?: string | null;
}

/** A wave's questionnaire logic from its survey.xml in Forsta (etl/fieldwork.py logic → /api/v1/waves/<id>/logic):
 *  when each question was shown, and the screen-out rules. Forsta waves only; 404 elsewhere. */
export interface WaveLogic { questions: Record<string, string>; terms: [string | null, string, string][] }
export const useLogic = (id: number) =>
  useQuery({ queryKey: ["logic", id], queryFn: () => get<WaveLogic>(`/api/v1/waves/${id}/logic`), ...forever, enabled: id > 0, retry: false });
/** An admin page's request (Fieldwork, Access). A demo sign-in also needs the admin token the Logs page keeps in this
 *  browser; an identity-provider sign-in does not (api/signin.py admin). */
function adminToken(): Record<string, string> {
  try { const token = localStorage.getItem("cip_admin_token"); return token ? { "X-CIP-Admin-Token": token } : {}; }
  catch { return {}; }   // a private window: no token
}
async function admin<T>(url: string, method = "GET", body?: unknown): Promise<T> {
  const r = await fetch(url, { method, credentials: "same-origin", body: body == null ? undefined : JSON.stringify(body),
                               headers: { "Content-Type": "application/json", ...adminToken() } });
  if (!r.ok) throw Object.assign(new Error((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`), { status: r.status });
  return r.json() as Promise<T>;
}
/** Admins get everything; a role the super admin let see Fieldwork gets it without the deletion schedule or emails. */
export const useFieldwork = (full: boolean) => useQuery({ queryKey: ["fieldwork", full], ...forever, retry: false,
  queryFn: () => full ? admin<FieldworkRecord>("/api/v1/admin/fieldwork") : get<FieldworkRecord>("/api/v1/fieldwork") });

/** The Forsta admin screens (screens/Forsta.tsx), built by etl/fieldwork.py publish_forsta from what Forsta gave. */
export interface ForstaLine { key: string; path: string; title: string | null; launched: string | null; state: string | null; hibernated: boolean;
  survey_id: number | null; reports: number; banners: number; files: number; splits: string[]; launch_warnings: number; warnings: Record<string, number>;
  check: { tables: number; cells: number; equal: number; differs: number } | null }
export interface ForstaOverview {
  surveys: ForstaLine[]; warnings_summary: Record<string, string | number | null>[];
  deletion: { path: string; title: string; date_of_deletion: string; days_until_deletion: number; created_on: string; created_by: string;
              last_access: string | null; risk_level: string | null }[];
  deletion_data: unknown[]; deleted: unknown[]; scheduled: unknown[]; planned: { autoclose: unknown[]; archives: unknown[] };
  retention: Record<string, number | null> | null; crosstab_defaults: Record<string, unknown> | null; categories: { text: string; key: string }[];
  endpoints: [string, string, string | null][]; not_loaded: { path: string; title: string | null; state: string | null }[]; collected: string | null;
}
export interface ForstaReport { id: string; title: string | null; description: string | null; access: string | null; updated: number | null; ran: boolean;
  exports: ("excel" | "pdf" | "pptx")[]; error: string | null; export_errors: Record<string, string>;
  columns: string[]; banner: string | null; tables: { label: string; title: string | null; rows: (string | number)[][] }[] }
export interface ForstaSurvey {
  path: string; title: string | null; hibernated: boolean; files: { filename: string; size: number; modified: string }[];
  banners: { title: string | null; segments: [string | null, string | null][] }[]; reports: ForstaReport[];
  splits: Record<string, { segments: string[]; rows: Record<string, (number | null)[]> }>;
  launch_warnings: Record<string, unknown[]>; warnings: { counts: Record<string, number>; events: [string, string, string | null, string | null][] };
  /** Forsta's own cross-tab against CIP's figures (etl/fieldwork.py check): [question, answer, Forsta, CIP] for each difference */
  check: { tables: number; cells: number; equal: number; differs: [string, string, number, number | null][]; not_compared: string[]; cip_only: string[] } | null;
  check_error: string | null;
}
export const useForsta = () => useQuery({ queryKey: ["forsta"], ...forever, retry: false, queryFn: () => admin<ForstaOverview>("/api/v1/admin/forsta") });
export const useForstaSurvey = (key: string) => useQuery({ queryKey: ["forsta", key], ...forever, retry: false, enabled: !!key,
  queryFn: () => admin<ForstaSurvey>(`/api/v1/admin/forsta/${key}`) });
const EXTENSION = { excel: "xlsx", pdf: "pdf", pptx: "pptx" };
/** A saved report's file (Excel, PDF or PowerPoint) as Forsta exported it, saved to the person's computer. */
export async function downloadForstaReport(key: string, report: string, name: string, format: keyof typeof EXTENSION) {
  const r = await fetch(`/api/v1/admin/forsta/${key}/export/${report}?format=${format}`, { credentials: "same-origin", headers: adminToken() });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`);
  save(await r.blob(), `${name}.${EXTENSION[format]}`);
}

/** The Access screen (super admin): every switchable menu, and each role's current choice (api/main.py roles). */
/** A role ("analyst"), a client ("client:acme") or one person ("person:ana@acme.com"), with their menus. */
export interface RoleMenus { features: { key: string; label: string }[];
  roles: { role: string; kind: "role" | "client" | "person"; label: string; features: string[]; chosen: boolean }[] }
export const useRoles = (person = "") => useQuery({ queryKey: ["roles", person], retry: false, placeholderData: keepPreviousData,
  queryFn: () => admin<RoleMenus>(`/api/v1/admin/roles${person ? `?person=${encodeURIComponent(person)}` : ""}`) });
export const saveRole = (role: string, features: string[]) =>
  admin<{ role: string; features: string[] }>(`/api/v1/admin/roles/${encodeURIComponent(role)}`, "PUT", { features });
/** A client or person back to the menus they inherit (their role's, or their client's). */
export const forgetRole = (role: string) => admin<{ role: string }>(`/api/v1/admin/roles/${encodeURIComponent(role)}`, "DELETE");

/** The Upload survey page (screens/Ingest.tsx, api/ingest.py): a week of the China survey from Baidu QSS. */
export interface SurveyCheck {
  wave: string | null; respondents: number; matched: number; problems: string[]; problem_count: number;
  field_start: string | null; field_end: string | null; median_seconds: number | null;
  questions: { qcode: string; text: string; type: "single" | "multi"; base: number; answers: [string, number, number][] }[];
}
export interface SurveyLoaded { survey_id: number; wave: string; respondents: number; matched: number }
/** Both files to preview (writes nothing) or publish; the API's words on a refusal become the error's message. */
export async function sendSurvey<T>(step: "preview" | "publish", raw: File, topline: File): Promise<T> {
  const body = new FormData();
  body.append("raw", raw);
  body.append("topline", topline);
  const r = await fetch(`/api/v1/admin/survey/${step}`, { method: "POST", credentials: "same-origin", headers: adminToken(), body });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}
