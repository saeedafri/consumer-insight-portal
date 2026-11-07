// The Access page (/app/access), the super admin only: which menus each role, each client and each chosen person
// sees, like choosing a subscription. A person's menus beat their client's, which beat their role's
// (shared/core/access.py menus). Drag a menu between "On the menu" and "Hidden" (Atlassian's pragmatic-drag-and-drop),
// or press its Show/Hide button from the keyboard, then Save. Reads GET /api/v1/admin/roles, saves PUT and drops
// DELETE /api/v1/admin/roles/<target> (api/main.py), stored in cip_role_access. It applies at once to the portal, the
// API keys and the MCP connector; an open page redraws its menu within minutes, and its data is refused at once.
import { useEffect, useRef, useState } from "react";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { forgetRole, queries, saveRole, useRoles } from "../api";
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
  const [role, setRole] = useState("analyst");
  const { data, error, isLoading, isPlaceholderData } = useRoles(role.startsWith("person:") ? role.slice(7) : "");
  const [person, setPerson] = useState("");
  const [picked, setPicked] = useState<Record<string, string[]>>({});   // unsaved choices, per role
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  if (isLoading) return <Card title="Access"><p className="sub">Loading…</p></Card>;
  if (error || !data) return <Card title="Access"><p className="sub">{(error as Error)?.message ?? "Not available"}. Only the super admin manages access.</p></Card>;

  const typed = data.roles.find((r) => r.role === role);
  if (role.startsWith("person:") && !typed && !isPlaceholderData) {   // not a person the portal lets in, or the super admin
    return <Card title="Access"><p className="sub">{role.slice(7)} cannot be given menus: the portal does not let that address in, or it is the super admin's.{" "}
      <button className="btn" type="button" onClick={() => setRole("analyst")}>Back</button></p></Card>;
  }
  const saved = typed ?? data.roles[0];
  const adding = saved.kind === "person" && !saved.chosen;   // a person typed in, not saved yet: starts from what they inherit
  const on = picked[saved.role] ?? saved.features;
  const changed = adding || (picked[saved.role] !== undefined && [...picked[saved.role]].sort().join() !== [...saved.features].sort().join());
  const set = (names: string[]) => { setPicked({ ...picked, [saved.role]: names }); setNote(""); };
  const show = (name: string) => set(on.includes(name) ? on : [...on, name]);
  const hide = (name: string) => set(on.filter((n) => n !== name));
  const save = async () => {
    setSaving(true);
    try {
      await saveRole(saved.role, on);
      await queries.invalidateQueries({ queryKey: ["roles"] });
      setPicked((all) => Object.fromEntries(Object.entries(all).filter(([name]) => name !== saved.role)));
      setNote("Saved. Data they lost is refused within a minute, and an open page redraws its menu within minutes.");
    } catch (e) { setNote((e as Error).message); }
    setSaving(false);
  };
  const forget = async () => {
    try {
      await forgetRole(saved.role);
      await queries.invalidateQueries({ queryKey: ["roles"] });
      setPicked((all) => Object.fromEntries(Object.entries(all).filter(([name]) => name !== saved.role)));
      if (saved.kind === "person") setRole("analyst");
      setNote(saved.kind === "person" ? `${saved.label} has their client's or role's menus again.` : "Back to the menus this client inherits.");
    } catch (e) { setNote((e as Error).message); }
  };
  const group = (kind: string, title: string) => {
    const list = data.roles.filter(r => r.kind === kind);
    return list.length > 0 && <div className="access-group"><span className="rail-label">{title}</span><div className="seg" role="group" aria-label={title}>
      {list.map((r) => <button key={r.role} type="button" aria-pressed={r.role === saved.role}
        onClick={() => { setRole(r.role); setNote(""); }}>{ROLE_NAMES[r.role] ?? r.label}{r.kind !== "role" && r.chosen ? " ·" : ""}</button>)}
    </div></div>;
  };

  return <div className="access">
    <header className="card-head">
      <div><h1>Access</h1>
        <p className="sub">Choose which menus a role, a client or one person sees. A person's menus beat their client's, which beat their role's. Drag a menu between the two columns, or use its Show and Hide button. The super admin always sees everything. Library, Overview, Methodology and What's new are always on.</p></div>
    </header>
    <div className="access-targets">
      {group("role", "Roles")}
      {group("client", "Clients")}
      {group("person", "People with their own menus")}
      <form className="access-group" onSubmit={e => { e.preventDefault(); if (person.includes("@")) { setRole(`person:${person.trim().toLowerCase()}`); setPerson(""); setNote(""); } }}>
        <label className="rail-label" htmlFor="access-person">Give one person their own menus (a trial, an exception)</label>
        <div className="access-add"><input id="access-person" type="email" placeholder="name@company.com" value={person} onChange={e => setPerson(e.target.value)} />
          <button className="btn" type="submit" disabled={!person.includes("@")}>Choose menus</button></div>
      </form>
    </div>
    <h2 className="access-who">{saved.kind === "person" ? `${saved.label}` : saved.kind === "client" ? `Client: ${saved.label}` : ROLE_NAMES[saved.role] ?? saved.label}
      <span className="sub">{saved.chosen ? " · menus chosen here" : saved.kind === "role" ? " · the role's package" : " · inherited until you save"}</span></h2>
    <div className="access-columns">
      <Column title="On the menu" note={`${on.length} of ${data.features.length}`} shown take={show}>
        {data.features.filter((f) => on.includes(f.key)).map((f) => <Menu key={f.key} name={f.key} label={f.label} shown flip={() => hide(f.key)} />)}
      </Column>
      <Column title="Hidden" note={saved.chosen || changed ? "Chosen here" : "Inherited (nothing chosen yet)"} shown={false} take={hide}>
        {data.features.filter((f) => !on.includes(f.key)).map((f) => <Menu key={f.key} name={f.key} label={f.label} shown={false} flip={() => show(f.key)} />)}
      </Column>
    </div>
    <p className="access-actions">
      <button className="btn primary" type="button" disabled={!changed || saving} onClick={save}>{saving ? "Saving…" : "Save"}</button>
      {changed && !adding && <button className="btn" type="button" onClick={() => set(saved.features)}>Undo changes</button>}
      {saved.kind !== "role" && saved.chosen && <button className="btn" type="button" onClick={forget}>Use the inherited menus</button>}
      <span className="sub" role="status">{note}</span>
    </p>
  </div>;
}
