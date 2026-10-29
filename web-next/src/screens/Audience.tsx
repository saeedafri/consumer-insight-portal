// Audiences: a group of respondents from any cuts and answers combined (e.g. Gen Z women who used GenAI to shop), shown
// against everyone else on any question with an index (120 = 20 % more likely), and what sets it apart across the wave.
import { useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { CUT_NAMES, myName, queries, send, useAudiences, useBook, useQuestion } from "../api";
import type { AudienceDef, AudienceProfile, AudienceResult, Book, Question } from "../api";
import { Card, Empty, Failure, Loading } from "../components/bits";
import QuestionNav from "../components/QuestionNav";
import { HIDDEN_BASE, HIDDEN_NOTE, pct } from "../stats";

const EMPTY: AudienceDef = { cuts: {}, answers: [] };
/** The audience from the link (?aud=), so Copy link and a saved view reproduce it; anything malformed is dropped.
 *  The link keeps conditions short (no question wording): the wording comes back from this wave's book. */
function readAudience(raw: string | null, book?: Book): AudienceDef {
  try {
    const d = JSON.parse(raw ?? "");
    const cuts = Object.fromEntries(Object.entries(d?.cuts ?? {}).filter(([k, v]) => CUT_NAMES[k] && Array.isArray(v) && v.every(x => typeof x === "string"))) as Record<string, string[]>;
    const answers = (Array.isArray(d?.answers) ? d.answers : []).filter((a: AudienceDef["answers"][number]) => typeof a?.qcode === "string" && typeof a.label === "string")
      .map((a: AudienceDef["answers"][number]) => ({ qcode: a.qcode, item_label: String(a.item_label ?? ""), option_code: typeof a.option_code === "number" ? a.option_code : null,
                     label: a.label, qtext: book?.questions.find(q => q.id === a.qcode)?.text ?? "" }));
    return { cuts, answers };
  } catch { return EMPTY; }
}
const writeAudience = (d: AudienceDef) => JSON.stringify({ cuts: d.cuts, answers: d.answers.map(({ qtext: _, ...a }) => a) });
/** What an answer condition stores: the row as srv_result names it (a multi item, or a single/grid option). */
const condition = (q: Question, groupLabel: string, row: { label: string; code: number | null }) => ({
  qcode: q.id, qtext: q.text, item_label: q.type.endsWith("multi") ? row.label : groupLabel, option_code: q.type.endsWith("multi") ? null : row.code,
  label: `${q.id}: ${groupLabel ? `${groupLabel} · ` : ""}${row.label}` });

export default function Audience() {
  const { id: raw, q: code } = useParams();
  const id = Number(raw);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { data: book, isLoading, error } = useBook(id);
  const question = useMemo(() => book?.questions.find(x => x.id === code) ?? book?.questions[0], [book, code]);
  const file = useQuestion(book?.wave, question?.id ?? "");
  const saved = useAudiences();
  const def = useMemo(() => readAudience(params.get("aud"), book), [params, book]);
  const setDef = (next: AudienceDef | ((d: AudienceDef) => AudienceDef)) => {
    const d = typeof next === "function" ? next(def) : next, p = new URLSearchParams(params);
    !Object.keys(d.cuts).length && !d.answers.length ? p.delete("aud") : p.set("aud", writeAudience(d));
    setParams(p, { replace: true });
  };
  const [name, setName] = useState("");
  const [pickQ, setPickQ] = useState("");
  const [pickA, setPickA] = useState("");
  const [result, setResult] = useState<AudienceResult | null>(null);
  const [profile, setProfile] = useState<AudienceProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  if (isLoading) return <Loading what="questions" />;
  if (error || !book) return <Failure error={error} />;
  if (!question) return <Empty>This wave has no questions with percentages.</Empty>;
  const values: Record<string, string[]> = {};
  for (const [dim, value] of file.data?.cuts ?? []) if (dim !== "total") (values[dim] ??= []).push(value);
  const toggle = (dim: string, value: string) => setDef(d => {
    const now = d.cuts[dim] ?? [];
    const next = now.includes(value) ? now.filter(v => v !== value) : [...now, value];
    const cuts = { ...d.cuts, [dim]: next };
    if (!next.length) delete cuts[dim];
    return { ...d, cuts };
  });
  const other = book.questions.find(x => x.id === pickQ);
  const options = other ? other.groups.flatMap(g => g.rows.map(r => ({ key: `${g.label}|${r.label}`, c: condition(other, g.label, r) }))) : [];
  const empty = !Object.keys(def.cuts).length && !def.answers.length;
  const run = async () => {
    setBusy(true); setNote("");
    try {
      const profiled = send<AudienceProfile>("POST", `/api/v1/waves/${id}/audience/profile`, { definition: def }).catch(() => null);
      setResult(await send<AudienceResult>("POST", `/api/v1/waves/${id}/audience`, { qcode: question.id, definition: def }));
      setProfile(await profiled);   // the profile is extra: without it the question's table still shows
    }
    catch (e) { setNote(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const save = async () => {
    if (!name.trim()) return setNote("Name the audience first.");
    try {
      await send("POST", "/api/v1/audiences", { name, definition: def, by: await myName() });
      setNote(`Saved “${name}” for the team.`); void queries.invalidateQueries({ queryKey: ["audiences"] });
    }
    catch (e) { setNote(e instanceof Error ? e.message : String(e)); }
  };
  return <div className="split">
    <QuestionNav questions={book.questions} current={question.id} onPick={q => { setResult(null); navigate(`/w/${id}/audience/${encodeURIComponent(q.id)}?${params}`); }} />
    <div className="stack">
      <Card as="h1" title="Build an audience" sub="Pick any groups and answers; everyone in the audience must match all of them. It is then shown against everyone else on the question on the right of the list.">
        {(saved.data?.length ?? 0) > 0 && <div className="toolbar">
          <label htmlFor="saved-aud" className="muted">Saved audiences</label>
          <select id="saved-aud" value="" onChange={e => { const a = saved.data!.find(x => String(x.audience_id) === e.target.value); if (a) { setDef(a.definition); setName(a.name); setResult(null); } }}>
            <option value="">Open one…</option>
            {saved.data!.map(a => <option key={a.audience_id} value={a.audience_id}>{a.name} · {a.created_by}</option>)}
          </select>
        </div>}
        <div className="audience-cuts">
          {Object.entries(values).map(([dim, vs]) => <fieldset key={dim}>
            <legend>{CUT_NAMES[dim] ?? dim}</legend>
            {vs.map(v => <label key={v} className="check"><input type="checkbox" checked={def.cuts[dim]?.includes(v) ?? false} onChange={() => toggle(dim, v)} /> {v}</label>)}
          </fieldset>)}
          {!Object.keys(values).length && <p className="muted">{file.isLoading ? "Loading groups…" : "This question has no demographic groups to pick from."}</p>}
        </div>
        <div className="toolbar" style={{ marginTop: 12 }}>
          <label className="sr-only" htmlFor="aud-q">Who gave an answer to</label>
          <select id="aud-q" value={pickQ} onChange={e => { setPickQ(e.target.value); setPickA(""); }} style={{ maxWidth: 360 }}>
            <option value="">Add: people who answered…</option>
            {book.questions.map(x => <option key={x.id} value={x.id}>{x.id}: {(x.short || x.text).slice(0, 70)}</option>)}
          </select>
          {other && <select aria-label="Answer" value={pickA} onChange={e => setPickA(e.target.value)} style={{ maxWidth: 320 }}>
            <option value="">…this answer</option>
            {options.map(o => <option key={o.key} value={o.key}>{o.c.label.replace(`${other.id}: `, "")}</option>)}
          </select>}
          {pickA && <button className="btn" onClick={() => { const o = options.find(x => x.key === pickA); if (o) setDef(d => ({ ...d, answers: [...d.answers, o.c] })); setPickQ(""); setPickA(""); }}>Add</button>}
        </div>
        {def.answers.length > 0 && <ul className="saved-views" style={{ marginTop: 8 }}>{def.answers.map((a, i) =>
          <li key={i}><span>{a.label}</span><button className="btn-chip" onClick={() => setDef(d => ({ ...d, answers: d.answers.filter((_, k) => k !== i) }))}>Remove</button></li>)}</ul>}
        <div className="toolbar" style={{ marginTop: 12, marginBottom: 0 }}>
          <button className="btn primary" disabled={empty || busy} onClick={() => void run()}>{busy ? "Counting…" : `Show ${question.id} for this audience`}</button>
          <label className="sr-only" htmlFor="aud-name">Audience name</label>
          <input id="aud-name" className="field" placeholder="Name it to save, e.g. Gen Z GenAI shoppers" value={name} onChange={e => setName(e.target.value)} style={{ minWidth: 220 }} />
          <button className="btn" disabled={empty} onClick={() => void save()}>Save for the team</button>
          {!empty && <button className="btn-chip" onClick={() => { setDef(EMPTY); setResult(null); setProfile(null); setName(""); }}>Clear</button>}
        </div>
        {note && <p className="muted" style={{ margin: "8px 0 0" }}>{note}</p>}
      </Card>
      {result && <Card title={`${question.id}: ${question.text}`} sub={`The audience against everyone else who answered. ▲▼ = different in a single 95 % comparison (not corrected for the many answers shown). Groups under ${HIDDEN_BASE} show no figure.${result.skipped.length ? ` Not applied in this wave (not asked, or the code means another question here): ${result.skipped.join(", ")}.` : ""}`}>
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Answer</th><th className="num">Audience</th><th className="num">Everyone else</th><th className="num">Difference</th><th className="num" title="100 × the audience's share ÷ everyone's: 120 = 20 % more likely than all respondents">Index</th></tr></thead>
          <tbody>{result.rows.map(([label, , base, share, rest, restBase, sig, index]) => <tr key={label}>
            <th scope="row">{label}</th>
            <td className="num">{share == null ? <span className="muted" title={`Fewer than ${HIDDEN_BASE} respondents on one side`}>{HIDDEN_NOTE}</span> : <><b>{pct(share)}</b><small style={{ display: "block" }} className="muted">n={base}</small></>}</td>
            <td className="num">{rest == null ? "–" : <>{pct(rest)}<small style={{ display: "block" }} className="muted">n={restBase}</small></>}</td>
            <td className={`num ${sig ? "sig" : "muted"}`}>{share == null || rest == null ? "–" : `${share - rest > 0 ? "+" : ""}${(share - rest).toFixed(1)} pts${sig ? (sig > 0 ? " ▲" : " ▼") : ""}`}</td>
            <td className={`num ${index != null && (index >= 120 || index <= 80) ? "sig" : "muted"}`}>{index ?? "–"}</td>
          </tr>)}</tbody>
        </table></div>
      </Card>}
      {profile && (profile.over.length > 0 || profile.under.length > 0) && <Card title="What sets this audience apart"
        sub={`Across every question in this wave: the answers this audience (${profile.size} people) gives most and least often compared with all respondents. Index 150 = 1.5 times as likely. Only significant differences on answers at least 5 % of everyone gives.`}>
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Question</th><th>Answer</th><th className="num">Audience</th><th className="num">Everyone</th><th className="num">Index</th></tr></thead>
          <tbody>{[...profile.over, ...profile.under].map(f => <tr key={`${f.qcode}|${f.answer}`}>
            <td><button className="btn-chip" onClick={() => navigate(`/w/${id}/audience/${encodeURIComponent(f.qcode)}?${params}`)}>{f.qcode}</button> <span className="muted">{f.question.slice(0, 80)}</span></td>
            <th scope="row">{f.answer}</th>
            <td className="num">{pct(f.pct)}</td>
            <td className="num">{pct(f.everyone)}</td>
            <td className="num sig">{f.index}{f.index > 100 ? " ▲" : " ▼"}</td>
          </tr>)}</tbody>
        </table></div>
      </Card>}
    </div>
  </div>;
}
