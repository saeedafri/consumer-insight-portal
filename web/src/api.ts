// The FastAPI contract (api/main.py, docs/Ui-Design-Claude/13 §5) and one cached hook per endpoint.
import { useQuery } from "@tanstack/react-query";

export type Column = "Total" | "Male" | "Female" | "Gen Z" | "Millennial" | "Gen X" | "Boomer";
export const COLUMNS: Column[] = ["Total", "Male", "Female", "Gen Z", "Millennial", "Gen X", "Boomer"];
export const CUT_OF: Record<Column, [string, string]> = {
  Total: ["total", "Total"], Male: ["gender", "Male"], Female: ["gender", "Female"], "Gen Z": ["generation", "GenZ"],
  Millennial: ["generation", "Millennial"], "Gen X": ["generation", "GenX"], Boomer: ["generation", "Boomer"],
};

export interface Wave {
  survey_id: number; title: string; wave_label: string; wave_date: string; survey_family: string;
  study_type: string; qualified_n: number; prior_survey_id: number | null; ly_survey_id: number | null;
  ly_status: "loaded" | "not_loaded" | "none"; modules?: string[];
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

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: "same-origin" });
  if (r.status === 401) { location.href = "/auth/dev-login?next=" + encodeURIComponent(location.pathname); throw new Error("Sign in required"); }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`);
  return r.json();
}

const forever = { staleTime: 5 * 60_000, gcTime: 30 * 60_000 };
export const useWaves = () => useQuery({ queryKey: ["waves"], queryFn: () => get<Wave[]>("/api/v1/waves"), ...forever });
export const useBook = (id: number) =>
  useQuery({ queryKey: ["book", id], queryFn: () => get<Book>(`/api/v1/waves/${id}/book`), ...forever, enabled: id > 0 });
export const useTrend = (id: number, q: string, dim = "total", value = "Total") =>
  useQuery({ queryKey: ["trend", id, q, dim, value], enabled: !!q, ...forever,
             queryFn: () => get<Trend>(`/api/v1/trend?survey_id=${id}&q=${encodeURIComponent(q)}&dim=${dim}&value=${encodeURIComponent(value)}`) });
export const useCrosstab = (id: number, q: string, by: [string, string], weeks: number, on: boolean) =>
  useQuery({ queryKey: ["crosstab", id, q, by, weeks], enabled: on && !!q, ...forever,
             queryFn: () => get<Crosstab>(`/api/v1/waves/${id}/crosstab?q=${encodeURIComponent(q)}&by=${by.join(",")}&weeks=${weeks}`) });
export const useSearch = (text: string) =>
  useQuery({ queryKey: ["search", text], enabled: text.trim().length >= 2, ...forever,
             queryFn: () => get<{ results: Hit[] }>(`/api/v1/search?q=${encodeURIComponent(text.trim())}&limit=60`) });

/** Rows of a question that make sense to rank: drops "None of these" / "Other – please specify". */
export const isFiller = (label: string) => /^(none of (these|the above)|other\s*[-–(]|prefer not)/i.test(label.trim());
