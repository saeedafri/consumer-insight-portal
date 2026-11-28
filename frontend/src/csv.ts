// Downloads a screen's table as CSV, Excel or PowerPoint, or a book of tables (a databank's every tab, a survey's every
// section, a tracker's every week) as one Excel workbook of tabs or one CSV (the Export button, components/bits.tsx
// ExportButtons). Excel and PowerPoint files are built by the API (api/exports.py). A cell starting with = + - @ is
// kept as text so Excel never runs it as a formula.
import { signIn } from "./api";

/** Save a blob under a file name; the URL is released after the click is handled (Safari and Firefox cancel it otherwise).
 *  Every download in the portal goes through here: a screen that released the URL at once lost its file in those browsers. */
export function save(blob: Blob, file: string) {
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: file });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/** A table as CSV text: what the screen shows, plus the question wording and base (as competitors' exports do). */
function csvText(header: string[], rows: (string | number | null | undefined)[][], notes: string[]) {
  const cell = (v: unknown) => {
    // text starting = + - @ (an answer label, a respondent's words) would run as a formula in Excel: keep it literal (a plain number stays a number)
    const s = v == null ? "" : typeof v === "string" && /^\s*[=+\-@]|^[\t\r]/.test(v) && !/^[+-]?\d+(\.\d+)?$/.test(v) ? `'${v}` : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [...notes.map(n => cell(n)), "", header.map(cell).join(","), ...rows.map(r => r.map(cell).join(","))].join("\n");
}

export function downloadCsv(name: string, header: string[], rows: (string | number | null | undefined)[][], notes: string[]) {
  save(new Blob(["﻿" + csvText(header, rows, notes)], { type: "text/csv" }), `${name}.csv`);
}

export type Format = "csv" | "xlsx" | "pptx" | "board";
export type TableSpec = { name: string; header: string[]; rows: (string | number | null)[][]; notes: string[] };
/** How Excel shows a table's numbers (api/exports.py write_sheet): unit "%" for a table of percentages, plain for the
 *  rows that are not (people asked, a net score; by index). A column whose header says % is percentages anyway. */
export type Style = { unit?: "%"; plain?: number[]; chart?: "line" | "column" };   // chart: a native Excel chart beside the table
/** One tab of a workbook: its title, table and style. */
export type Sheet = Style & { title: string; header: string[]; rows: (string | number | null)[][]; notes: string[] };

/** The same table as CSV (built here), an Excel workbook or a PowerPoint slide (built by the API from these rows), or
 * pinned to a board as it is now (components/PinDialog listens). */
export async function downloadTable(format: Format, name: string, header: string[], rows: (string | number | null | undefined)[][], notes: string[], style: Style = {}) {
  if (format === "csv") return downloadCsv(name, header, rows, notes);
  if (format === "board") {
    const spec: TableSpec = { name, header, rows: rows.map(r => r.map(c => (c === undefined ? null : c))), notes };
    return void window.dispatchEvent(new CustomEvent<TableSpec>("cip:pin", { detail: spec }));
  }
  return fetchExport(format, name, { name, header, rows: rows.map(r => r.map(c => (c === undefined ? null : c))), notes, ...style });
}

/** Every tab of a databank or every section of a survey in one download: an Excel workbook with a tab per table, a
 *  PowerPoint deck with a slide per table (both built by the API), or one CSV with the tables one under another. */
export async function downloadBook(format: Format, name: string, sheets: Sheet[]) {
  if (format === "board") return;   // a book is not pinned: its screen passes pin={false} to ExportButtons
  if (format === "csv") {
    const text = sheets.map(t => csvText(t.header, t.rows, [t.title, ...t.notes])).join("\n\n");
    return save(new Blob(["﻿" + text], { type: "text/csv" }), `${name}.csv`);
  }
  return fetchExport(format, name, { name, sheets });
}

/** The Excel workbook or PowerPoint deck the API builds from a table or a book (api/exports.py), saved under its name. */
async function fetchExport(format: string, name: string, body: object) {
  const response = await fetch(`/api/v1/export/${format}`, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body) });
  if (response.status === 401) signIn();
  if (!response.ok) throw new Error(`Export failed (${response.status})`);
  save(await response.blob(), `${name}.${format}`);
}
