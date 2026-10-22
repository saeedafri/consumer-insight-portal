// The FastAPI contract (api/main.py, docs/Ui-Design-Claude/13 §5) and one cached hook per endpoint.
import { useQuery } from "@tanstack/react-query";
import { perf } from "./perf";

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
  country?: string; platform?: "forsta" | "qualtrics" | "surveymonkey"; source_ref?: string;
  field_start?: string | null; field_end?: string | null;   // UTC; recorded for Forsta waves only
  events?: string[];     // recurring retail events in the title (config/survey_calendar.yml events), e.g. Prime Day
}

// A module dashboard (api/dashboards.py, config/dashboards.yml): the business team's "this week at a glance"
export interface Metric { label: string; segment: string; pct: number | null; n: number | null; base: number;   // pct, n: null under 30 people
                          vs_prior: number | null; vs_ly: number | null; ly_pct: number | null; flags: string[] }
export interface WaveRef { survey_id: number | null; wave_no: number; season: number; week_of: string; loaded: boolean }
export interface Dashboard {
  dashboard: string; title: string; wave: WaveRef; prior: WaveRef | null; last_year: WaveRef | null; ly_rule: string;
  tiles: Record<string, Metric | null>; lists: Record<string, Metric[]>; segments: Record<string, Metric[]>;
  takeaways: string[]; small_base: number; data_as_of: string | null;
  tile_labels?: Record<string, string>; highlights?: { list: string; title: string; of: string }[]; prior_label?: string;
}
export interface Row extends Partial<Record<Column, number | null>> {   // null: under 30 people, no figure
  label: string; code: number | null; prior: number | null; prior_base: number | null;
  ly: number | null; ly_base: number | null; flags: string;
}
export interface Group { label: string; base: number; bases: Partial<Record<Column, number>>; rows: Row[] }
export interface Question {
  id: string; text: string; short: string | null; type: "single" | "multi" | "grid_single" | "grid_multi";
  section: string; base_desc: string | null; groups: Group[];
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

async function get<T>(url: string): Promise<T> {
  const deregister = perf.registerPendingApi(url);
  const t0 = performance.now();
  let status = 0;
  let serverDur: number | null = null;
  let size: number | null = null;

  try {
    const r = await fetch(url, { credentials: "same-origin" });
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

    if (r.status === 401) { location.href = "/auth/dev-login?next=" + encodeURIComponent(location.pathname); throw new Error("Sign in required"); }
    if (r.status === 503) throw new Busy();   // admission control: the query client waits and retries
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`);
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
export const useBook = (id: number) =>
  useQuery({ queryKey: ["book", id], queryFn: () => get<Book>(`/api/v1/waves/${id}/book`), ...forever, enabled: id > 0 });
export const useDashboard = (code: string | undefined, id: number) =>
  useQuery({ queryKey: ["dashboard", code, id], enabled: !!code && id > 0, ...forever,
             queryFn: () => get<Dashboard>(`/api/v1/dashboards/${code}/${id}`) });
/** One question across every wave of its family and every cut, as compact columns (app/data/payloads.question_from):
 *  cell k is waves[w[k]] × cuts[c[k]] × answers[a[k]], n[k] people of b[k]. Compare and Trends slice it on screen. */
export interface QuestionFile {
  qcode: string; waves: [number, string, number][]; versions: string[];   // [survey_id, date, version]; wording per version
  answers: [string, number | null, string][]; cuts: [string, string][];   // [item_label, code, label]; [dim, value]
  w: number[]; c: number[]; a: number[]; n: (number | null)[]; b: number[];   // n: null under 30 people
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
  if (r.status === 401) { location.href = "/auth/dev-login?next=" + encodeURIComponent(location.pathname); throw new Error("Sign in required"); }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`);
  return (r.status === 204 ? null : r.json()) as T;
}

export interface TeamView { view_id: number; name: string; url: string; note: string | null; saved_by: string; created_at: string }
export interface Alert { alert_id: number; name: string; qcode: string; answer_label: string; dim: string; dim_value: string; against: "prior" | "ly";
                         created_by: string; created_at: string; last_fired: number | null }
export interface AudienceDef { cuts: Record<string, string[]>; answers: { qcode: string; qtext: string; item_label: string; option_code: number | null; label: string }[] }
export interface Audience { audience_id: number; name: string; definition: AudienceDef; created_by: string }
export interface AudienceResult { qcode: string; multi: boolean; skipped: string[]; rows: [string, number | null, number, number | null, number | null, number, number][] }
export interface Answer { answer: string; no_source: boolean; mode: "claude" | "figures" | "none";
                          sources: { id: string; survey_id: number; wave_date: string; title: string; qcode: string; question: string; base: number; answers: [string, number][]; link: string }[] }
export interface BoardSummary { board_id: number; name: string; created_by: string; created_at: string; items: number }
export interface BoardComment { comment_id: number; author: string; body: string; created_at: string }
export interface BoardItem { item_id: number; title: string; url: string; data_version: string; added_by: string; added_at: string;
                             spec: { name: string; header: string[]; rows: (string | number | null)[][]; notes: string[] }; comments: BoardComment[] }
export interface Board { board_id: number; name: string; created_by: string; created_at: string; current_version: string; items: BoardItem[] }
export const useBoards = () => useQuery({ queryKey: ["boards"], queryFn: () => get<BoardSummary[]>("/api/v1/boards") });
export const useBoard = (id: number) => useQuery({ queryKey: ["board", id], queryFn: () => get<Board>(`/api/v1/boards/${id}`) });
export const useTeamViews = () => useQuery({ queryKey: ["team-views"], queryFn: () => get<TeamView[]>("/api/v1/team/views") });
export const useAlerts = () => useQuery({ queryKey: ["alerts"], queryFn: () => get<Alert[]>("/api/v1/alerts") });
export const useAudiences = () => useQuery({ queryKey: ["audiences"], queryFn: () => get<Audience[]>("/api/v1/audiences") });

/** Who is saving: asked once, kept in this browser (there is no sign-in yet). */
export function myName(): string | null {
  let name: string | null = null;
  try { name = localStorage.getItem("cip_name"); } catch { /* private window */ }
  if (!name) {
    name = window.prompt("Your name, so the team sees who saved it:")?.trim() || null;
    try { if (name) localStorage.setItem("cip_name", name); } catch { /* not kept */ }
  }
  return name;
}
