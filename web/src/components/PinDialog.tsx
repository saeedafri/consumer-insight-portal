// "Board" on any table: pin it, as it is now, to a team board (api/team.py). Mounted once in the shell; every
// screen's export buttons raise "cip:pin" with the table they would download (csv.ts).
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { queries, send, useBoards } from "../api";
import type { TableSpec } from "../csv";

export default function PinDialog() {
  const dialog = useRef<HTMLDialogElement>(null);
  const [spec, setSpec] = useState<TableSpec | null>(null);
  const [board, setBoard] = useState("");
  const [newName, setNewName] = useState("");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState<{ text: string; board?: number } | null>(null);
  const boards = useBoards(spec != null);   // read only while the dialog is open, not on every screen

  useEffect(() => {
    const open = (e: Event) => {
      const table = (e as CustomEvent<TableSpec>).detail;
      setSpec(table); setTitle(table.notes[0] ?? table.name); setNote(null);
      void queries.invalidateQueries({ queryKey: ["boards"] });   // a board a colleague made since is offered too
      dialog.current?.showModal();
    };
    window.addEventListener("cip:pin", open);
    return () => window.removeEventListener("cip:pin", open);
  }, []);
  useEffect(() => { if (!board && boards.data?.length) setBoard(String(boards.data[0].board_id)); }, [boards.data, board]);

  const pin = async () => {
    if (!spec) return;
    try {
      let id = Number(board);
      if (board === "new" || !boards.data?.length) {
        if (!newName.trim()) return setNote({ text: "Name the new board." });
        id = (await send<{ board_id: number }>("POST", "/api/v1/boards", { name: newName })).board_id;
        setBoard(String(id)); setNewName("");
      }
      await send("POST", `/api/v1/boards/${id}/items`, { title, url: location.pathname + location.search, spec });
      await queries.invalidateQueries({ queryKey: ["boards"] });
      await queries.invalidateQueries({ queryKey: ["board", id] });
      setNote({ text: "Pinned with today's numbers.", board: id });
    } catch (e) { setNote({ text: e instanceof Error ? e.message : String(e) }); }
  };
  const creating = board === "new" || !boards.data?.length;
  return <dialog ref={dialog} className="pin-dialog" aria-labelledby="pin-title" onClose={() => setSpec(null)}>
    <form method="dialog" onSubmit={e => { e.preventDefault(); void pin(); }}>
      <h3 id="pin-title">Pin to a board</h3>
      <p className="muted">The numbers are kept as they are now, with the data version, so the board reads the same next month.</p>
      <label htmlFor="pin-title-input">Title</label>
      <input id="pin-title-input" value={title} maxLength={300} onChange={e => setTitle(e.target.value)} />
      <label htmlFor="pin-board">Board</label>
      <select id="pin-board" value={creating ? "new" : board} onChange={e => setBoard(e.target.value)}>
        {boards.data?.map(b => <option key={b.board_id} value={b.board_id}>{b.name} ({b.items})</option>)}
        <option value="new">New board…</option>
      </select>
      {creating && <input aria-label="New board name" placeholder="e.g. Holiday read-out" value={newName} maxLength={200} onChange={e => setNewName(e.target.value)} />}
      {note && <p className="muted" role="status">{note.text} {note.board != null && <Link to={`/boards/${note.board}`} onClick={() => dialog.current?.close()}>Open the board</Link>}</p>}
      <div className="pin-actions">
        <button type="button" className="btn" onClick={() => dialog.current?.close()}>Close</button>
        <button type="submit" className="btn primary">Pin</button>
      </div>
    </form>
  </dialog>;
}
