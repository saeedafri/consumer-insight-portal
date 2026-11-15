// The Access page (/app/access), the super admin only: which menus each role, each client and each chosen person
// sees, like choosing a subscription. A person's menus beat their client's, which beat their role's
// (shared/core/access.py menus). The menus are the left menu itself, group by group with each menu's own pages
// (config/access.yml menu): tick one, or a group or a menu with pages to tick all of it, then Save. Reads GET
// /api/v1/admin/roles, saves PUT and drops DELETE /api/v1/admin/roles/<target> (api/main.py), stored in
// cip_role_access. It applies at once to the portal, the API keys and the MCP connector; an open page redraws its menu
// within minutes, and its data is refused at once.
import { useEffect, useRef, useState } from "react";
import { forgetRole, queries, saveRole, useRoles } from "../api";
import type { MenuNode } from "../api";
import { Card } from "../components/bits";

const ROLE_NAMES: Record<string, string> = { analyst: "Analysts (Coresight staff)", client: "Clients" };

/** Every feature under these entries: their own keys and their pages'. */
const keysOf = (nodes: MenuNode[]): string[] => nodes.flatMap(n => [...(n.key ? [n.key] : []), ...keysOf(n.children ?? [])]);

/** One tick box for some menus: ticked when all are on, half-ticked when some are (a group, a menu with pages). */
function Tick({ label, keys, on, flip, locked }: { label: string; keys: string[]; on: string[]; flip: (keys: string[], to: boolean) => void; locked?: string }) {
  const box = useRef<HTMLInputElement>(null);
  const all = keys.length > 0 && keys.every(k => on.includes(k)), some = keys.some(k => on.includes(k));
  useEffect(() => { if (box.current) box.current.indeterminate = some && !all; }, [some, all]);
  return <label className={`access-tick${locked ? " locked" : ""}`}>
    <input ref={box} type="checkbox" checked={locked ? true : all} disabled={!!locked} onChange={() => flip(keys, !all)} />
    <span>{label}</span>{locked && <span className="sub"> · {locked}</span>}
  </label>;
}

/** A group's menus as the left menu lists them, each menu's own pages under it. */
function Branch({ nodes, on, flip }: { nodes: MenuNode[]; on: string[]; flip: (keys: string[], to: boolean) => void }) {
  return <ul className="access-branch">{nodes.map(n => <li key={n.key ?? n.label}>
    <Tick label={n.label} keys={keysOf([n])} on={on} flip={flip}
          locked={n.always ? "always on" : n.admin ? "the super admin's alone" : undefined} />
    {n.children && n.children.length > 0 && <Branch nodes={n.children} on={on} flip={flip} />}
  </li>)}</ul>;
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
  const flip = (keys: string[], to: boolean) => set(to ? [...new Set([...on, ...keys])] : on.filter(n => !keys.includes(n)));
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
        <p className="sub">Choose which menus a role, a client or one person sees: the left menu, group by group, with each menu's own pages. Tick a group or a menu with pages to tick all of it. A person's menus beat their client's, which beat their role's. Turning off Shopping & Spending or the China weekly tracker takes its waves out of the Library, Search and Ask too. The super admin always sees everything; Home and a wave's Overview are always on.</p></div>
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
    <div className="access-tree">
      {data.menu.map(g => { const keys = keysOf(g.items); return <fieldset key={g.group} className="access-menu-group">
        <legend><Tick label={g.group} keys={keys} on={on} flip={flip} /><span className="sub">{keys.filter(k => on.includes(k)).length} of {keys.length}</span></legend>
        <Branch nodes={g.items} on={on} flip={flip} />
      </fieldset>; })}
    </div>
    <p className="access-actions">
      <button className="btn primary" type="button" disabled={!changed || saving} onClick={save}>{saving ? "Saving…" : "Save"}</button>
      {changed && !adding && <button className="btn" type="button" onClick={() => set(saved.features)}>Undo changes</button>}
      {saved.kind !== "role" && saved.chosen && <button className="btn" type="button" onClick={forget}>Use the inherited menus</button>}
      <span className="sub" role="status">{note}</span>
    </p>
  </div>;
}
