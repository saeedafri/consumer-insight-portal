// One question across the waves an analyst picks, by one cut: every cell with its base, a change only where it is
// significant, and the waves where this question code meant something else listed, never mixed in.
import { useMemo } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { CUT_NAMES, useBook, useQuestion, useWaves } from "../api";
import type { QuestionFile } from "../api";
import { answerLabel, cellsOf, withJoined } from "../question";
import type { Cell, Cells } from "../question";

type Shown = Cell & { pct: number };
const shown = (c: Cell | undefined): c is Shown => c?.pct != null;   // has a figure (HIDDEN_BASE or more people)
import { Card, copyLink, Empty, Failure, IconLink, Menu, Skeleton, SkeletonScreen, SourceLine, sourceText, ExportButtons , QuestionCode } from "../components/bits";
import type { Wave } from "../api";
import QuestionNav from "../components/QuestionNav";
import QuestionTabs from "../components/QuestionTabs";
import { downloadTable } from "../csv";
import type { Format } from "../csv";
import { direction, fmtDate, HIDDEN_BASE as HIDDEN, pct, pts, significant, SMALL_BASE } from "../stats";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const LAST = [4, 8, 13];
const PICKS = [...LAST.map(String), "event", "own"];

export default function Compare() {
  const { id: raw, q: code } = useParams();
  const id = Number(raw);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { data: book, isLoading, error } = useBook(id);
  const question = useMemo(() => book?.questions.find(x => x.id === code) ?? book?.questions[0], [book, code]);
  const dim = params.get("cut") && CUT_NAMES[params.get("cut")!] ? params.get("cut")! : "total";
  const file = useQuestion(book?.wave, question?.id ?? "");   // every wave and cut: picking waves or a cut is local
  const joined = useMemo(() => file.data && withJoined(file.data), [file.data]);   // the wording's weeks under other codes too
  const cells = useMemo(() => joined && cellsOf(joined), [joined]);
  const waves = useWaves().data;
  if (isLoading) return <SkeletonScreen kind="question" />;
  if (error || !book) return <Failure error={error} />;
  if (!question) return <Empty>This wave has no questions with percentages.</Empty>;
  const set = (k: string, v: string | null) => {
    const p = new URLSearchParams(params);
    v ? p.set(k, v) : p.delete(k);
    setParams(p, { replace: true });
  };
  const events = waves?.find(w => w.survey_id === id)?.events ?? [];
  return <div className="split">
    <QuestionNav questions={book.questions} current={question.id} onPick={q => navigate(`/w/${id}/compare/${encodeURIComponent(q.id)}?${params}`)} />
    <div className="stack">
      <Card>
        <div className="breadcrumb qcrumbs"><Link to={`/w/${id}`}>Overview</Link><span className="sep">›</span><span>Compare waves</span><span className="sep">›</span><QuestionCode q={question} /></div>
        <h1 className="qtext">{question.text}</h1>
        <div className="toolbar" style={{ marginBottom: 0, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Tabs value={PICKS.includes(params.get("pick") ?? "") ? params.get("pick")! : "4"} onValueChange={v => set("pick", v)}>
            <TabsList>
              {LAST.map(n => (
                <TabsTrigger key={n} value={String(n)}>Last {n}</TabsTrigger>
              ))}
              {events.length > 0 && (
                <TabsTrigger value="event" title={`Waves whose title names ${events.join(" or ")}`}>
                  Same event: {events.join(", ")}
                </TabsTrigger>
              )}
              <TabsTrigger value="own">Pick waves</TabsTrigger>
            </TabsList>
          </Tabs>
          <select aria-label="Cut" value={dim} onChange={e => set("cut", e.target.value === "total" ? null : e.target.value)}>
            <option value="total">Total only</option>
            {Object.entries(CUT_NAMES).map(([k, label]) => <option key={k} value={k}>By {label.toLowerCase()}</option>)}
          </select>
        </div>
        <QuestionTabs id={id} q={question.id} />
      </Card>
      {file.error ? <Failure error={file.error} /> : !joined || !cells ? <Skeleton height={420} className="card" label="waves to compare" />
        : <Table f={joined} cell={cells} dim={dim} current={id} events={events} titles={new Map(waves?.map(w => [w.survey_id, w]) ?? [])} from={{ ...book.wave, weighting: "unweighted" }} />}
    </div>
  </div>;
}

function Table({ f, cell, dim, current, events, titles, from }: { f: QuestionFile; cell: Cells; dim: string; current: number; events: string[];
  titles: Map<number, { title: string; events?: string[] }>; from: Wave }) {
  const [params, setParams] = useSearchParams();
  const me = f.waves.findIndex(w => w[0] === current);
  const version = f.waves[me]?.[2];
  const eligible = f.waves.map(([survey_id, wave_date, v], i) => ({ survey_id, wave_date, v, i })).filter(w => w.v === version && w.i <= me);
  const joined = new Set(f.joined?.waves.map(w => w.join("|")));   // the wording's weeks under other codes: not this code's
  const others = f.waves.filter(w => w[2] !== version && !joined.has(w.join("|"))).map(([survey_id, wave_date, v]) => ({ survey_id, wave_date, text: f.versions[v - 1] }));
  const d = { qcode: f.qcode, dim, not_comparable: others };
  const pick = PICKS.includes(params.get("pick") ?? "") ? params.get("pick")! : "4";
  const listed = (params.get("waves") ?? "").split(",").map(Number).filter(Boolean);
  const own = listed.length ? listed : eligible.slice(-4).map(w => w.survey_id);   // picking starts from the last 4
  const chosen = pick === "own" ? eligible.filter(w => own.includes(w.survey_id) || w.survey_id === current)
    : pick === "event" ? eligible.filter(w => titles.get(w.survey_id)?.events?.some(e => events.includes(e)))
    : eligible.slice(-Number(pick));
  const toggle = (sid: number) => {
    const p = new URLSearchParams(params);
    const next = own.includes(sid) ? own.filter(x => x !== sid) : [...own, sid];
    p.set("waves", next.join(","));
    setParams(p, { replace: true });
  };
  const label = (a: number) => answerLabel(f.answers[a]);
  const lastIdx = chosen.at(-1)?.i ?? me;
  // answers the shown waves gave: an answer only older waves had ("Bought groceries online" in 2021) is a row of dashes
  const ranked = f.answers.map((_, k) => k).filter(k => chosen.some(w => cell(w.i, 0, k)))
    .sort((x, y) => (cell(lastIdx, 0, y)?.pct ?? -1) - (cell(lastIdx, 0, x)?.pct ?? -1));
  const asked = Number(params.get("ans"));   // from a shared link: anything not an answer of this version falls back
  const answer = ranked.includes(asked) ? asked : ranked[0] ?? 0;
  const byCut = dim !== "total";
  // rows: answers for Total; with a cut, the chosen answer for Total and each value of the cut
  const rows = byCut ? f.cuts.map(([cd, v], c) => ({ key: v, name: v, c, a: answer, keep: c === 0 || cd === dim })).filter(r => r.keep)
    : ranked.map(k => ({ key: String(k), name: label(k), c: 0, a: k }));
  const exportAs = (format: Format) => downloadTable(format, `${f.qcode}-compare${byCut ? `-${dim}` : ""}`,
    [byCut ? CUT_NAMES[dim] : "Answer", ...chosen.flatMap(w => [`${w.wave_date} %`, `${w.wave_date} base`])],
    rows.map(r => [r.name, ...chosen.flatMap(w => { const c = cell(w.i, r.c, r.a); return shown(c) ? [c.pct, c.base] : ["", c?.base ?? ""]; })]),
    [`${f.qcode}: ${f.versions[version - 1]}`, ...(byCut ? [`Answer: ${label(answer)}`] : []), `Waves: ${chosen.map(w => w.wave_date).join(", ")}`,
     `Cells under n=${HIDDEN} hidden`, "▲▼: single comparison with the wave to the left, 95 %, not corrected for multiple tests",
     sourceText(from, fmtDate(chosen.at(-1)?.wave_date ?? f.waves[me][1]), "n per cell")]);
  if (eligible.length < 2) return <Card><Empty>Only this wave asked this question in this wording, so there is nothing to compare it with.{d.not_comparable.length ? " The waves below used the same code for a different question." : ""}</Empty><Other d={d} /></Card>;
  return <>
    {pick === "own" && <Card title="Pick waves" sub={`${eligible.length} waves asked this question in this wording, up to this one`}>
      <div className="pick-waves">{[...eligible].reverse().map(w => <label key={w.survey_id} className="check">
        <input type="checkbox" checked={w.survey_id === current || own.includes(w.survey_id)} disabled={w.survey_id === current} onChange={() => toggle(w.survey_id)} />
        {fmtDate(w.wave_date)}</label>)}</div>
    </Card>}
    <Card title={`${chosen.length} waves${byCut ? ` by ${CUT_NAMES[dim].toLowerCase()}` : ""}`}
          sub={`Each cell: share and its base. ▲▼ = different from the wave to its left in a single 95 % comparison, not corrected for the many cells compared. Faded = under ${SMALL_BASE} respondents.`}
          aside={<div className="toolbar" style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
            {byCut && <select aria-label="Answer" value={answer} onChange={e => { const p = new URLSearchParams(params); p.set("ans", e.target.value); setParams(p, { replace: true }); }}>
              {ranked.map(k => <option key={k} value={k}>{label(k)}</option>)}</select>}
            <ExportButtons onExport={exportAs} />
            <Menu label="" icon={<span aria-hidden>⋯</span>} keep>
              <button onClick={e => copyLink(e.currentTarget)}><IconLink /> <span>Copy link</span></button>
            </Menu>
          </div>}>
      {chosen.length < 2 ? <Empty>Pick at least one more wave.</Empty> : <div className="table-wrap"><table className="data compare">
        <thead><tr><th>{byCut ? CUT_NAMES[dim] : "Answer"}</th>
          {chosen.map(w => <th key={w.survey_id} className="num" title={titles.get(w.survey_id)?.title}>{fmtDate(w.wave_date)}</th>)}
          <th className="num">First → last</th></tr></thead>
        <tbody>{rows.map(r => {
          const cells = chosen.map(w => cell(w.i, r.c, r.a));
          const first = cells.find(shown), last = [...cells].reverse().find(shown);
          const sigAll = first && last && first !== last && significant(last.pct, last.base, first.pct, first.base);
          return <tr key={r.key}><th scope="row">{r.name}</th>
            {cells.map((c, k) => {
              if (!c) return <td key={k} className="num muted" title="Nobody in this group answered in this wave">–</td>;
              if (!shown(c)) return <td key={k} className="num muted" title={`Only ${c.base} respondents: hidden`}>n&lt;{HIDDEN}</td>;
              const before = cells.slice(0, k).reverse().find(shown);
              const move = before && significant(c.pct, c.base, before.pct, before.base) ? (c.pct > before.pct ? "▲" : "▼") : "";
              return <td key={k} className={`num ${c.base < SMALL_BASE ? "small" : ""}`}>
                <b>{pct(c.pct)}</b>{move && <span className={move === "▲" ? "up" : "down"}> {move}</span>}<small>n={c.base}</small></td>;
            })}
            <td className={`num ${first && last && first !== last ? direction(last.pct - first.pct) : "muted"}`}>{first && last && first !== last ? pts(last.pct - first.pct) : "–"}{sigAll ? " ●" : ""}</td>
          </tr>;
        })}</tbody>
      </table></div>}
      <SourceLine wave={fmtDate(chosen.at(-1)?.wave_date ?? f.waves[me][1])} base="n per cell" from={from}
                  extra={`${chosen.length} waves${f.codes?.length ? ` · earlier waves asked it as ${f.codes.join(", ")}` : ""} · cells under ${HIDDEN} hidden · ▲▼ single comparisons, not corrected`} />
    </Card>
    <Other d={d} />
  </>;
}

/** The other questions this code was used for: one line per question with its waves and dates (one line per wave
 *  repeated the same wording eight times, 15 Nov 2026). Newest question first. */
function Other({ d }: { d: { qcode: string; not_comparable: { survey_id: number; wave_date: string; text: string }[] } }) {
  if (!d.not_comparable.length) return null;
  const asked = new Map<string, { wave_date: string }[]>();
  for (const w of d.not_comparable) asked.set(w.text, [...(asked.get(w.text) ?? []), w]);   // oldest first, as the file lists them
  const questions = [...asked].sort((x, y) => y[1].at(-1)!.wave_date.localeCompare(x[1].at(-1)!.wave_date));
  return <Card title="Not compared: a different question under the same code"
               sub={`${d.not_comparable.length} waves used ${d.qcode} to ask ${questions.length === 1 ? "another question" : `${questions.length} other questions`}. They are left out.`}>
    <ul style={{ margin: 0, paddingLeft: 18 }}>
      {questions.map(([text, ws]) => <li key={text}><b>{ws.length} wave{ws.length === 1 ? "" : "s"}, {fmtDate(ws[0].wave_date)}{ws.length > 1 ? ` – ${fmtDate(ws.at(-1)!.wave_date)}` : ""}</b>: <span className="muted">“{text.length > 140 ? text.slice(0, 139) + "…" : text}”</span></li>)}
    </ul>
  </Card>;
}
