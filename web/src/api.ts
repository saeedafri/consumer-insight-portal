// The FastAPI contract (api/main.py, docs/Ui-Design-Claude/13 §5) and one cached hook per endpoint.
import { useQuery } from "@tanstack/react-query";

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
}

// A module dashboard (api/dashboards.py, config/dashboards.yml): the business team's "this week at a glance"
export interface Metric { label: string; segment: string; pct: number; n: number; base: number; vs_prior: number | null;
                          vs_ly: number | null; ly_pct: number | null; flags: string[] }
export interface WaveRef { survey_id: number | null; wave_no: number; season: number; week_of: string; loaded: boolean }
export interface Dashboard {
  dashboard: string; title: string; wave: WaveRef; prior: WaveRef | null; last_year: WaveRef | null; ly_rule: string;
  tiles: Record<string, Metric | null>; lists: Record<string, Metric[]>; segments: Record<string, Metric[]>;
  takeaways: string[]; small_base: number; data_as_of: string | null;
}
export interface Row extends Partial<Record<Column, number>> {
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
  qcode: string; dim: string; value: string; waves: { survey_id: number; wave_date: string }[];
  series: { item_label: string; code: number | null; label: string; pct: (number | null)[]; base: (number | null)[] }[];
}
export interface Crosstab {
  survey_id: number; qcode: string; by: [string, string]; weeks: number;
  waves: { survey_id: number; wave_date: string }[]; warnings: string[];
  columns: string[]; rows: (string | number | null)[][];
}
export interface Hit { qcode: string; text: string; type: string; family: string; first: string; last: string; waves: number; survey_id: number; title: string }

/** The server asked us to come back in a few seconds (a burst of uncached requests). */
export class Busy extends Error { constructor() { super("The portal is busy; retrying in a few seconds…"); } }

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: "same-origin" });
  if (r.status === 401) { location.href = "/auth/dev-login?next=" + encodeURIComponent(location.pathname); throw new Error("Sign in required"); }
  if (r.status === 503) throw new Busy();   // admission control: the query client waits and retries
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`);
  return r.json();
}

const forever = { staleTime: 5 * 60_000, gcTime: 30 * 60_000 };
export const useWaves = () => useQuery({ queryKey: ["waves"], queryFn: () => get<Wave[]>("/api/v1/waves"), ...forever });
export const useBook = (id: number) =>
  useQuery({ queryKey: ["book", id], queryFn: () => get<Book>(`/api/v1/waves/${id}/book`), ...forever, enabled: id > 0 });
export const useDashboard = (code: string | undefined, id: number) =>
  useQuery({ queryKey: ["dashboard", code, id], enabled: !!code && id > 0, ...forever,
             queryFn: () => get<Dashboard>(`/api/v1/dashboards/${code}/${id}`) });
/** A question across its tracker family: a published static file for multi-wave families (served by nginx). */
export const useTrend = (wave: Wave | undefined, q: string, dim = "total", value = "Total") =>
  useQuery({ queryKey: ["trend", wave?.survey_family, wave?.study_type, q, dim, value], enabled: !!q && !!wave, ...forever,
             queryFn: () => get<Trend>(`/api/v1/trends/${[wave!.survey_family, wave!.study_type, q, dim, value].map(encodeURIComponent).join("/")}`) });
export const useCrosstab = (id: number, q: string, by: [string, string], weeks: number, on: boolean) =>
  useQuery({ queryKey: ["crosstab", id, q, by, weeks], enabled: on && !!q, ...forever,
             queryFn: () => get<Crosstab>(`/api/v1/waves/${id}/crosstab?q=${encodeURIComponent(q)}&by=${by.join(",")}&weeks=${weeks}`) });
export const useSearch = (text: string) =>
  useQuery({ queryKey: ["search", text], enabled: text.trim().length >= 2, ...forever,
             queryFn: () => get<{ results: Hit[]; understood: { corrected: string[]; expanded: string[]; matched_by: string } }>(`/api/v1/search?q=${encodeURIComponent(text.trim())}&limit=60`) });

/** Rows of a question that make sense to rank: drops "None of these" / "Other – please specify". */
export const isFiller = (label: string) => /^(none of (these|the above)|other\s*[-–(]|prefer not)/i.test(label.trim());
