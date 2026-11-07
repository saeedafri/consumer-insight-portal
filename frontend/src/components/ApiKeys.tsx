// The Account page's "API keys and Claude" card (screens/Account.tsx): make, list and revoke your own keys for the
// portal's API and its MCP connector (Claude and other AI assistants). A key acts as you, with your access as it is at
// each request: what your menus hide, your keys cannot read either. Calls /api/v1/keys (api/main.py); the key is shown
// once, here, and only its fingerprint is kept (shared/core/api_keys.py).
import { useState } from "react";
import { queries, send, useKeys } from "../api";
import { Card } from "./bits";

export default function ApiKeys() {
  const { data } = useKeys();
  const [name, setName] = useState("");
  const [made, setMade] = useState<{ key: string; name: string } | null>(null);
  const [note, setNote] = useState("");
  const portal = location.origin;
  const refresh = () => queries.invalidateQueries({ queryKey: ["keys"] });
  const make = async () => {
    try { setMade(await send<{ key: string; name: string }>("POST", "/api/v1/keys", { name })); setName(""); setNote(""); }
    catch (e) { setNote((e as Error).message); }
    void refresh();
  };
  const revoke = async (shown: string) => {
    try { await send("DELETE", `/api/v1/keys/${shown}`); setNote("Revoked: it stopped working at once."); }
    catch (e) { setNote((e as Error).message); }
    void refresh();
  };
  return <Card title="API keys and Claude" sub="Use the portal from your own programs, or from Claude and other AI assistants (MCP). A key acts as you: it reads only what your menus show, and loses anything you lose at once.">
    {made && <div className="key-made" role="status">
      <p><b>{made.name}</b>: copy this key now. It is shown once; CIP keeps only its fingerprint.</p>
      <code className="key">{made.key}</code>
      <p className="muted small">Claude Code: <code>claude mcp add --transport http cip {portal}/mcp --header "Authorization: Bearer {made.key.slice(0, 8)}…"</code> (with the whole key). Other tools: send <code>Authorization: Bearer &lt;key&gt;</code> to {portal}/api/v1/… or {portal}/mcp.</p>
      <button className="btn" type="button" onClick={() => { void navigator.clipboard?.writeText(made.key); setNote("Copied."); }}>Copy key</button>{" "}
      <button className="btn" type="button" onClick={() => setMade(null)}>Done</button>
    </div>}
    {data && data.keys.length > 0 && <div className="table-wrap"><table className="data">
      <thead><tr><th>Name</th><th>Key</th><th>Made</th><th /></tr></thead>
      <tbody>{data.keys.map(k => <tr key={k.shown}><th scope="row">{k.name}</th><td><code>{k.shown}…</code></td><td>{k.created}</td>
        <td><button className="btn" type="button" onClick={() => revoke(k.shown)} aria-label={`Revoke ${k.name}`}>Revoke</button></td></tr>)}</tbody>
    </table></div>}
    <form className="access-add" onSubmit={e => { e.preventDefault(); void make(); }} style={{ marginTop: 12 }}>
      <input aria-label="Name for the new key" placeholder="Name it after its tool, e.g. My Claude" value={name} onChange={e => setName(e.target.value)} maxLength={60} />
      <button className="btn primary" type="submit" disabled={!name.trim()}>Make a key</button>
    </form>
    {note && <p className="muted small" role="status">{note}</p>}
  </Card>;
}
