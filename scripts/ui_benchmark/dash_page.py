"""Same screen in Dash: stateless callbacks, the database aggregates, run under gunicorn workers."""
import os, sqlite3
from functools import lru_cache
from dash import Dash, Input, Output, dash_table, dcc, html

DB = os.environ["NAIVE_DB"]
SECTORS = ["Apparel", "Beauty", "Department", "Dollar", "Electronics", "Grocery", "Home", "Sporting"]


@lru_cache(maxsize=64)
def sector_summary(sector: str) -> tuple:
    con = sqlite3.connect(DB)
    return tuple(con.execute("select state, count(*), sum(revenue), sum(closed = 0) from stores where sector = ? group by state", (sector,)).fetchall())


app = Dash(__name__)
server = app.server
app.layout = html.Div([dcc.Dropdown(SECTORS, "Apparel", id="sector"), html.H3(id="open"), dcc.Graph(id="chart"), dash_table.DataTable(id="table")])


@app.callback(Output("open", "children"), Output("chart", "figure"), Output("table", "data"), Input("sector", "value"))
def show(sector):
    rows = sector_summary(sector)
    states = [r[0] for r in rows]
    return (f"Stores open {sum(r[3] for r in rows):,}",
            {"data": [{"type": "bar", "x": states, "y": [r[1] for r in rows]}]},
            [{"state": r[0], "stores": r[1], "revenue": r[2]} for r in rows])
