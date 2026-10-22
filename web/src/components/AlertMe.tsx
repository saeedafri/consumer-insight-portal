// "Alert me": tell the team on Teams when this answer moves significantly against the previous wave or last year
// (api/team.py; the pipeline checks every alert once per new wave, same question wording only, 30+ people each side to be tested).
import { useState } from "react";
import { myName, send } from "../api";
import type { Group, Question } from "../api";

export default function AlertMe({ surveyId, question, group }: { surveyId: number; question: Question; group: Group }) {
  const [open, setOpen] = useState(false);
  const [row, setRow] = useState(0);
  const [against, setAgainst] = useState<"prior" | "ly">("prior");
  const [note, setNote] = useState("");
  const multi = question.type.endsWith("multi");
  const save = async () => {
    const r = group.rows[row], by = myName();
    if (!by) return setNote("Your name is needed so the team knows whose alert it is.");
    const answer = group.label ? `${group.label} · ${r.label}` : r.label;
    try {
      await send("POST", "/api/v1/alerts", { survey_id: surveyId, qcode: question.id, item_label: multi ? r.label : group.label,
        option_code: multi ? null : r.code, answer_label: answer, name: `${question.id} · ${answer}`, against, by });
      setNote(`Alert set: the team hears on Teams, and you by email, when “${answer}” moves significantly.`);
    } catch (e) { setNote(e instanceof Error ? e.message : String(e)); }
  };
  if (!open) return <button className="btn" onClick={() => setOpen(true)} title="Get a Teams message when an answer moves significantly">Alert me</button>;
  return <div className="alert-me" role="group" aria-label="Set an alert">
    <label htmlFor="alert-row" className="muted">Alert when</label>
    <select id="alert-row" value={row} onChange={e => setRow(Number(e.target.value))}>
      {group.rows.map((r, i) => <option key={r.label} value={i}>{r.label}</option>)}
    </select>
    <span className="muted">moves significantly vs</span>
    <select aria-label="Baseline" value={against} onChange={e => setAgainst(e.target.value as "prior" | "ly")}>
      <option value="prior">the previous wave</option><option value="ly">the same week last year</option>
    </select>
    <button className="btn primary" onClick={() => void save()}>Set alert</button>
    <button className="btn-chip" onClick={() => { setOpen(false); setNote(""); }}>Close</button>
    {note && <span className="muted" style={{ flexBasis: "100%" }}>{note}</span>}
  </div>;
}
