// The question list every analysis screen shares: grouped by section, filterable by text or code.
import { useMemo, useState } from "react";
import type { Question } from "../api";

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
    return [...out];
  }, [questions, filter]);
  return <nav className="qnav" aria-label="Questions">
    <label className="sr-only" htmlFor="qfilter">Filter questions</label>
    <input id="qfilter" type="search" value={filter} onChange={e => setFilter(e.target.value)} placeholder={`Filter ${questions.length} questions…`} />
    <div className="qnav-list">
      {sections.map(([section, qs]) => <div key={section}>
        <h4>{section}</h4>
        {qs.map(q => <button key={q.id} className={q.id === current ? "on" : ""} aria-current={q.id === current} onClick={() => onPick(q)}>
          <code>{q.id}</code><span>{q.short || q.text}</span>
        </button>)}
      </div>)}
      {!sections.length && <p className="muted pad">No question matches “{filter}”.</p>}
    </div>
  </nav>;
}
