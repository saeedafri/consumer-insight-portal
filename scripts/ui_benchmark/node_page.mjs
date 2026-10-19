// Same screen as api_page.py on Node's built-in http + sqlite (no packages): the Node.js baseline.
import http from "node:http";
import { DatabaseSync } from "node:sqlite";

const db = new DatabaseSync(process.env.NAIVE_DB, { readOnly: true });
const query = db.prepare("select state, count(*) n, sum(revenue) revenue, sum(closed = 0) open from stores where sector = ? group by state");
const cache = new Map();

function summary(sector) {
  if (!cache.has(sector)) {
    const rows = query.all(sector);
    cache.set(sector, JSON.stringify({ open: rows.reduce((a, r) => a + r.open, 0), states: rows.map(r => ({ state: r.state, stores: r.n, revenue: r.revenue })) }));
  }
  return cache.get(sector);
}

const page = `<!doctype html><body><div id=app>Loading</div><script>
fetch('/api/summary/Apparel').then(r=>r.json()).then(d=>{document.getElementById('app').innerHTML=
'<h3>Stores open '+d.open.toLocaleString()+'</h3><table>'+d.states.map(s=>'<tr><td>'+s.state+'</td><td>'+s.stores+'</td></tr>').join('')+'</table>';});
</script></body>`;

http.createServer((req, res) => {
  const m = req.url.match(/^\/api\/summary\/(\w+)$/);
  if (m) { res.writeHead(200, { "content-type": "application/json" }); return res.end(summary(m[1])); }
  res.writeHead(200, { "content-type": "text/html" });
  res.end(page);
}).listen(Number(process.env.PORT || 8692));
