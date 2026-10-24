import { signIn } from "./api";

/** Save a blob under a file name; the URL is released after the click is handled (Safari and Firefox cancel it otherwise). */
function save(blob: Blob, file: string) {
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: file });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// Download any table as CSV: what the screen shows, plus the question wording and base (as competitors' exports do).
export function downloadCsv(name: string, header: string[], rows: (string | number | null | undefined)[][], notes: string[]) {
  const cell = (v: unknown) => {
    // text starting = + - @ (an answer label, a respondent's words) would run as a formula in Excel: keep it literal (a plain number stays a number)
    const s = v == null ? "" : typeof v === "string" && /^\s*[=+\-@]|^[\t\r]/.test(v) && !/^[+-]?\d+(\.\d+)?$/.test(v) ? `'${v}` : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const text = [...notes.map(n => cell(n)), "", header.map(cell).join(","), ...rows.map(r => r.map(cell).join(","))].join("\n");
  save(new Blob(["﻿" + text], { type: "text/csv" }), `${name}.csv`);
}

export type Format = "csv" | "xlsx" | "pptx" | "board";
export type TableSpec = { name: string; header: string[]; rows: (string | number | null)[][]; notes: string[] };

/** The same table as CSV (built here), an Excel workbook or a PowerPoint slide (built by the API from these rows), or
 * pinned to a board as it is now (components/PinDialog listens). */
export async function downloadTable(format: Format, name: string, header: string[], rows: (string | number | null | undefined)[][], notes: string[]) {
  if (format === "csv") return downloadCsv(name, header, rows, notes);
  if (format === "board") {
    const spec: TableSpec = { name, header, rows: rows.map(r => r.map(c => (c === undefined ? null : c))), notes };
    return void window.dispatchEvent(new CustomEvent<TableSpec>("cip:pin", { detail: spec }));
  }
  const response = await fetch(`/api/v1/export/${format}`, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, header, rows: rows.map(r => r.map(c => (c === undefined ? null : c))), notes }) });
  if (response.status === 401) signIn();
  if (!response.ok) throw new Error(`Export failed (${response.status})`);
  save(await response.blob(), `${name}.${format}`);
}
