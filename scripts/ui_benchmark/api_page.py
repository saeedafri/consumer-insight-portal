"""Same screen, recommended pattern: the database aggregates, the service returns only the summary."""
import os, sqlite3
from functools import lru_cache
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

DB = os.environ["NAIVE_DB"]
app = FastAPI()

@lru_cache(maxsize=64)
def sector_summary(sector: str) -> dict:
    con = sqlite3.connect(DB)
    rows = con.execute("select state, count(*), sum(revenue), sum(closed = 0) from stores where sector = ? group by state", (sector,)).fetchall()
    return {"open": sum(r[3] for r in rows), "states": [{"state": r[0], "stores": r[1], "revenue": r[2]} for r in rows]}

@app.get("/api/summary/{sector}")
def summary(sector: str):
    return JSONResponse(sector_summary(sector))

@app.get("/")
def page():
    return HTMLResponse("""<!doctype html><body><div id=app>Loading</div><script>
fetch('/api/summary/Apparel').then(r=>r.json()).then(d=>{document.getElementById('app').innerHTML=
'<h3>Stores open '+d.open.toLocaleString()+'</h3><table>'+d.states.map(s=>'<tr><td>'+s.state+'</td><td>'+s.stores+'</td></tr>').join('')+'</table>';});
</script></body>""")
