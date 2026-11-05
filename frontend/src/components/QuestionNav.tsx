// The question list every analysis screen shares: grouped by section, filterable by text or code. On a phone it is
// a "Question ▾" button that opens the same list as a sheet, so the chart is the first thing on the screen.
import { useEffect, useMemo, useRef, useState } from "react";
import type { Question } from "../api";
import { SMALL_BASE } from "../stats";
import Profiled from "./Profiled";
import { X } from "lucide-react";

export default function QuestionNav({ questions, current, onPick }:
  { questions: Question[]; current?: string; onPick: (q: Question) => void }) {
  const [filter, setFilter] = useState("");
  const sections = useMemo(() => {
    const words = filter.toLowerCase().split(/\s+/).filter(Boolean);
    const out = new Map<string, Question[]>();
    for (const q of questions) {
      const hay = `${q.id} ${q.text}`.toLowerCase();
      if (words.every(w => hay.includes(w))) out.set(q.section, [...(out.get(q.section) ?? []), q]);
    }
    return [...out].sort(([a], [b]) => a.localeCompare(b));
  }, [questions, filter]);
  const [sheet, setSheet] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = dialog.current;
    if (sheet && d && !d.open) d.showModal();
  }, [sheet]);
  const pick = (q: Question) => { dialog.current?.close(); onPick(q); };
  const at = questions.findIndex(q => q.id === current);
  const here = questions[at];
  const list = (where: string) => <nav className="qnav" aria-label="Questions">
      <label className="sr-only" htmlFor={`qfilter-${where}`}>Filter questions</label>
      <div style={{ position: "relative", margin: "12px 12px 6px" }}>
        <input
          id={`qfilter-${where}`}
          type="search"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder={`Filter ${questions.length} questions…`}
          style={{ width: "100%", margin: 0, paddingRight: filter ? 28 : 10, boxSizing: "border-box" }}
        />
        {filter && (
          <button
            type="button"
            onClick={() => setFilter("")}
            aria-label="Clear filter"
            style={{
              position: "absolute",
              right: 6,
              top: "50%",
              transform: "translateY(-50%)",
              background: "transparent",
              border: 0,
              color: "var(--ink-2)",
              cursor: "pointer",
              padding: "2px",
              display: "inline-flex",
              alignItems: "center"
            }}
          >
            <X size={14} />
          </button>
        )}
      </div>
      <div className="qnav-list">
        {sections.map(([section, qs]) => <div key={section}>
          <h4>{section}</h4>
          {qs.map(q => <button key={q.id} className={q.id === current ? "on" : ""} aria-current={q.id === current} onClick={() => pick(q)}>
            <code>{q.id}</code><span>{q.short || q.text}</span>
            <small className={q.groups[0].base < SMALL_BASE ? "small" : ""} title="Respondents who answered">n={q.groups[0].base}</small>
          </button>)}
        </div>)}
        {!sections.length && <p className="muted pad">No question matches “{filter}”.</p>}
      </div>
    </nav>;
  return <Profiled id="QuestionNav">
    <button className="qnav-open" onClick={() => setSheet(true)} aria-haspopup="dialog">
      {here && <code>{here.id}</code>}<span>{here ? here.short || here.text : "Questions"}</span><small>{at + 1} of {questions.length}</small><span aria-hidden className="caret">▾</span>
    </button>
    {list("side")}
    <dialog ref={dialog} className="qsheet" aria-label="Questions" onClose={() => setSheet(false)}
            onClick={e => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
      {sheet && list("sheet")}
    </dialog>
  </Profiled>;
}
