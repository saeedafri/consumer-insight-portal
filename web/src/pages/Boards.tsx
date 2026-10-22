// Boards: tables pinned with the numbers they had then (the data version says which publish), a comment thread on
// each, and the whole board as one branded PowerPoint deck. Pinned numbers never change; "Open live" shows today's.
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { send, useBoard, useBoards } from "../api";
import type { BoardItem } from "../api";
import { Card, Empty, Failure, IconDownload, Loading } from "../components/bits";
import { fmtDate } from "../stats";

const day = (iso: string) => fmtDate(iso.slice(0, 10));
const tables = (n: number) => `${n} ${n === 1 ? "table" : "tables"}`;

export default function Boards() {
  const { id } = useParams();
  return id ? <OneBoard id={Number(id)} /> : <AllBoards />;
}

function AllBoards() {
  const { data, error, isLoading, refetch } = useBoards();
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const navigate = useNavigate();
  const create = async () => {
    try { navigate(`/boards/${(await send<{ board_id: number }>("POST", "/api/v1/boards", { name })).board_id}`); }
    catch (e) { setNote(e instanceof Error ? e.message : String(e)); }
  };
  if (isLoading) return <Loading what="boards" />;
  if (error) return <Failure error={error} />;
  return <div className="stack">
    <div className="page-head"><div><h1>Boards</h1>
      <p className="lede">Pin any table with <b>Board</b> next to its downloads. Each board keeps the numbers as pinned, takes comments, and downloads as one deck.</p></div></div>
    <Card title="New board">
      <form className="row-form" onSubmit={e => { e.preventDefault(); void create(); }}>
        <input aria-label="Board name" placeholder="e.g. Holiday read-out" value={name} maxLength={200} onChange={e => setName(e.target.value)} />
        <button className="btn primary" type="submit" disabled={!name.trim()}>Create</button>
        {note && <span className="muted" role="status">{note}</span>}
      </form>
    </Card>
    {!data?.length ? <Empty>No boards yet.</Empty> : <Card title={`${data.length} boards`}>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Board</th><th className="num">Tables</th><th>By</th><th>Created</th></tr></thead>
        <tbody>{data.map(b => <tr key={b.board_id}>
          <td><Link to={`/boards/${b.board_id}`}>{b.name}</Link></td><td className="num">{b.items}</td>
          <td>{b.created_by}</td><td>{day(b.created_at)}</td></tr>)}</tbody>
      </table></div>
      <button className="btn-chip" onClick={() => void refetch()}>Refresh</button>
    </Card>}
  </div>;
}

function OneBoard({ id }: { id: number }) {
  const { data, error, isLoading } = useBoard(id);
  const queries = useQueryClient();
  const navigate = useNavigate();
  const [note, setNote] = useState("");
  const act = async (method: "POST" | "DELETE", url: string, body?: unknown) => {
    try { await send(method, url, body); setNote(""); await queries.invalidateQueries({ queryKey: ["board", id] }); return true; }
    catch (e) { setNote(e instanceof Error ? e.message : String(e)); return false; }
  };
  if (isLoading) return <Loading what="the board" />;
  if (error) return <Failure error={error} />;
  if (!data) return null;
  return <div className="stack">
    <div className="page-head"><div><h1>{data.name}</h1>
      <p className="lede"><Link to="/boards">All boards</Link> · by {data.created_by} · {day(data.created_at)} · {tables(data.items.length)}</p></div>
      <div className="head-actions">
        {data.items.length > 0 && <a className="btn primary" href={`/api/v1/boards/${id}/deck`}><IconDownload /> Download deck</a>}
        <button className="btn" onClick={() => void send("DELETE", `/api/v1/boards/${id}`).then(() => {
          queries.removeQueries({ queryKey: ["board", id] }); void queries.invalidateQueries({ queryKey: ["boards"] }); navigate("/boards");
        }, (e: Error) => setNote(e.message))}>Delete board</button>
      </div>
      {note && <p className="muted" role="status" style={{ flexBasis: "100%" }}>{note}</p>}
    </div>
    {!data.items.length ? <Empty>Nothing pinned yet: open any question and press <b>Board</b> next to its downloads.</Empty>
      : data.items.map(item => <Pinned key={item.item_id} item={item} current={data.current_version} act={act} />)}
  </div>;
}

function Pinned({ item, current, act }: { item: BoardItem; current: string;
                                          act: (method: "POST" | "DELETE", url: string, body?: unknown) => Promise<boolean> }) {
  const [text, setText] = useState("");
  const { header, rows, notes } = item.spec;
  const shown = header.map((_, j) => j).filter(j => j === 0 || rows.some(r => r[j] != null && r[j] !== ""));   // drop an empty column (a one-group crosstab's "Group")
  const cell = (row: (string | number | null)[], c: string | number | null) => c == null || c === "" ? "–" : typeof c !== "number" ? c
    : row.some(x => typeof x === "string" && x.startsWith("Base")) ? c.toLocaleString("en-US") : c.toFixed(1);   // bases are counts
  return <Card title={item.title} as="h2" sub={<>Pinned {day(item.added_at)} by {item.added_by}
      {item.data_version !== current && <> · <span className="chip warn">data republished since</span></>}</>}
    aside={<div className="head-actions"><Link className="btn" to={item.url}>Open live</Link>
      <button className="btn" onClick={() => void act("DELETE", `/api/v1/boards/items/${item.item_id}`)}>Remove</button></div>}>
    <div className="table-wrap"><table className="data">
      <thead><tr>{shown.map(j => <th key={j} className={j && rows.some(r => typeof r[j] === "number") ? "num" : undefined}>{header[j]}</th>)}</tr></thead>
      <tbody>{rows.slice(0, 40).map((r, i) => <tr key={i}>{shown.map(j => <td key={j} className={typeof r[j] === "number" ? "num" : undefined}>
        {cell(r, r[j])}</td>)}</tr>)}</tbody>
    </table></div>
    {rows.length > 40 && <p className="muted">First 40 of {rows.length} rows; the deck and the live screen have all.</p>}
    <p className="source-line">{notes.slice(1).join(" · ")}</p>
    <section className="comments" aria-label="Comments">
      {item.comments.map(c => <p key={c.comment_id} className="comment"><b>{c.author}</b> <span className="muted">{day(c.created_at)}</span><br />{c.body}
        <button className="btn comment-delete" aria-label={`Delete ${c.author}'s comment`} onClick={() => void act("DELETE", `/api/v1/boards/comments/${c.comment_id}`)}>Delete</button></p>)}
      <form className="row-form" onSubmit={e => { e.preventDefault(); void act("POST", `/api/v1/boards/items/${item.item_id}/comments`, { body: text }).then(ok => ok && setText("")); }}>
        <input aria-label="Add a comment" placeholder="Add a comment for the team" value={text} maxLength={2000} onChange={e => setText(e.target.value)} />
        <button className="btn" type="submit" disabled={!text.trim()}>Comment</button>
      </form>
    </section>
  </Card>;
}
