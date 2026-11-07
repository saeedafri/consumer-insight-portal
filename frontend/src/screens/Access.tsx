// The Access page (/app/access), the super admin only: which menus each role sees, like choosing a subscription.
// Drag a menu between "On the menu" and "Hidden" (Atlassian's pragmatic-drag-and-drop), or press its Show/Hide button
// from the keyboard, then Save. Reads GET /api/v1/admin/roles and saves PUT /api/v1/admin/roles/<role> (api/main.py),
// stored in cip_role_access; shared/core/access.py profile() applies it to every API answer within 30 s, and the
// left menu (components/Shell.tsx) follows on the person's next page load.
import { useEffect, useRef, useState } from "react";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { queries, saveRole, useRoles } from "../api";
import { Card } from "../components/bits";

const ROLE_NAMES: Record<string, string> = { analyst: "Analysts (Coresight staff)", client: "Clients" };

/** One menu as a card: dragged with the mouse or touch, moved with its button from the keyboard. */
function Menu({ name, label, shown, flip }: { name: string; label: string; shown: boolean; flip: () => void }) {
  const card = useRef<HTMLLIElement>(null);
  const [dragging, setDragging] = useState(false);
  useEffect(() => draggable({ element: card.current!, getInitialData: () => ({ name }),
                              onDragStart: () => setDragging(true), onDrop: () => setDragging(false) }), [name]);
  return <li ref={card} className={`access-menu${dragging ? " dragging" : ""}`}>
    <span>{label}</span>
    <button className="btn" type="button" onClick={flip} aria-label={`${shown ? "Hide" : "Show"} ${label}`}>{shown ? "Hide" : "Show"}</button>
  </li>;
}

/** A column that takes the menus dropped on it. */
function Column({ title, note, shown, children, take }: { title: string; note: string; shown: boolean; children: React.ReactNode; take: (name: string) => void }) {
  const zone = useRef<HTMLElement>(null);
  const [over, setOver] = useState(false);
  useEffect(() => dropTargetForElements({ element: zone.current!, getData: () => ({ shown }),
    onDragEnter: () => setOver(true), onDragLeave: () => setOver(false),
    onDrop: ({ source }) => { setOver(false); take(String(source.data.name)); } }), [shown, take]);
  return <section ref={zone} className={`access-column${over ? " over" : ""}`} aria-label={title}>
    <h2>{title}</h2><p className="sub">{note}</p>
    <ul>{children}</ul>
  </section>;
}

export default function Access() {
  const { data, error, isLoading } = useRoles();
  const [role, setRole] = useState("analyst");
  const [picked, setPicked] = useState<Record<string, string[]>>({});   // unsaved choices, per role
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  if (isLoading) return <Card title="Access"><p className="sub">Loading…</p></Card>;
  if (error || !data) return <Card title="Access"><p className="sub">{(error as Error)?.message ?? "Not available"}. Only the super admin manages access.</p></Card>;

  const saved = data.roles.find((r) => r.role === role) ?? data.roles[0];
  const on = picked[saved.role] ?? saved.features;
  const changed = picked[saved.role] !== undefined && [...picked[saved.role]].sort().join() !== [...saved.features].sort().join();
  const set = (names: string[]) => { setPicked({ ...picked, [saved.role]: names }); setNote(""); };
  const show = (name: string) => set(on.includes(name) ? on : [...on, name]);
  const hide = (name: string) => set(on.filter((n) => n !== name));
  const save = async () => {
    setSaving(true);
    try {
      await saveRole(saved.role, on);
      await queries.invalidateQueries({ queryKey: ["roles"] });
      setPicked((all) => Object.fromEntries(Object.entries(all).filter(([name]) => name !== saved.role)));
      setNote("Saved. People in this role see the new menus on their next page load (the data follows within 30 seconds).");
    } catch (e) { setNote((e as Error).message); }
    setSaving(false);
  };

  return <div className="access">
    <header className="card-head">
      <div><h1>Access</h1>
        <p className="sub">Choose which menus each role sees. Drag a menu between the two columns, or use its Show and Hide button. The super admin always sees everything. Library, Overview, Methodology and What's new are always on.</p></div>
    </header>
    <div className="seg" role="group" aria-label="Role">
      {data.roles.map((r) => <button key={r.role} type="button" aria-pressed={r.role === saved.role}
        onClick={() => { setRole(r.role); setNote(""); }}>{ROLE_NAMES[r.role] ?? r.role}</button>)}
    </div>
    <div className="access-columns">
      <Column title="On the menu" note={`${on.length} of ${data.features.length}`} shown take={show}>
        {data.features.filter((f) => on.includes(f.key)).map((f) => <Menu key={f.key} name={f.key} label={f.label} shown flip={() => hide(f.key)} />)}
      </Column>
      <Column title="Hidden" note={saved.chosen || changed ? "Chosen here" : "The role's package (nothing chosen yet)"} shown={false} take={hide}>
        {data.features.filter((f) => !on.includes(f.key)).map((f) => <Menu key={f.key} name={f.key} label={f.label} shown={false} flip={() => show(f.key)} />)}
      </Column>
    </div>
    <p className="access-actions">
      <button className="btn primary" type="button" disabled={!changed || saving} onClick={save}>{saving ? "Saving…" : "Save"}</button>
      {changed && <button className="btn" type="button" onClick={() => set(saved.features)}>Undo changes</button>}
      <span className="sub" role="status">{note}</span>
    </p>
  </div>;
}
