"""The site's files as the API serves them (api/main.py SinglePageApp), on servers without nginx in front (this Mac's
live link): a file the build also gzipped goes out gzipped to a browser that accepts it, plain to one that does not,
and a repeat visit with the same ETag gets a 304. Also the build step that announces the portal's code in its page."""
import gzip
import subprocess
from pathlib import Path

from starlette.testclient import TestClient

from api.main import SinglePageApp


def test_gzipped_copy_is_sent_when_the_browser_accepts_it(tmp_path):
    script = b"console.log('chart library');" * 200
    (tmp_path / "chart.js").write_bytes(script)
    (tmp_path / "chart.js.gz").write_bytes(gzip.compress(script))
    client = TestClient(SinglePageApp(directory=tmp_path, html=True))

    packed = client.get("/chart.js", headers={"Accept-Encoding": "gzip"})
    assert packed.status_code == 200 and packed.headers["content-encoding"] == "gzip"
    assert packed.content == script and "javascript" in packed.headers["content-type"]   # the client unzips it
    assert int(packed.headers["content-length"]) < len(script) / 10

    plain = client.get("/chart.js", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers and plain.content == script
    assert plain.headers["vary"] == packed.headers["vary"] == "Accept-Encoding"

    again = client.get("/chart.js", headers={"Accept-Encoding": "gzip", "If-None-Match": packed.headers["etag"]})
    assert again.status_code == 304


def test_build_announces_the_portal_code_the_first_scripts_load(tmp_path):
    """frontend/scripts/preload-portal.mjs (npm run build): the files named inside the page's first scripts are
    preloaded from the page's <head>; files the HTML already names are not repeated."""
    chunks = tmp_path / "out/_next/static/chunks"
    chunks.mkdir(parents=True)
    (chunks / "runtime.js").write_text('load("static/chunks/portal.js", "static/chunks/portal.css", "static/chunks/runtime.js")')
    (chunks / "portal.js").write_text("")
    (tmp_path / "out/app").mkdir()
    page = tmp_path / "out/app/index.html"
    page.write_text('<!DOCTYPE html><html><head><script src="/_next/static/chunks/runtime.js"></script></head></html>')
    script = Path(__file__).resolve().parents[1] / "frontend/scripts/preload-portal.mjs"
    subprocess.run(["node", str(script)], cwd=tmp_path, check=True, capture_output=True)
    html = page.read_text()
    assert '<head><link rel="preload" as="script" href="/_next/static/chunks/portal.js"/>' in html
    assert '<link rel="preload" as="style" href="/_next/static/chunks/portal.css"/>' in html
    assert html.count("runtime.js") == 1


def test_a_missing_file_is_a_404_and_is_not_cached_for_a_year(tmp_path, monkeypatch):
    """The Python file server (servers without nginx): only a path with no file ending is the app's page; a missing
    script is a 404; and the immutable one-year cache header (api/main.py every_request) goes only on files that exist."""
    import api.main as main
    monkeypatch.setattr(main, "WEB", tmp_path)   # the folder the app fallback looks in
    (tmp_path / "404.html").write_text("not found")   # the Next.js build has one: StaticFiles answers a miss with it
    (tmp_path / "app").mkdir()
    (tmp_path / "app/index.html").write_text("<html>portal</html>")
    (tmp_path / "_next/static").mkdir(parents=True)
    (tmp_path / "_next/static/real.js").write_text("1")
    web = main.FastAPI()
    web.middleware("http")(main.every_request)
    web.mount("/", SinglePageApp(directory=tmp_path, html=True))
    client = TestClient(web)
    assert client.get("/app/w/530/").text == "<html>portal</html>"
    assert client.get("/app/missing.js").status_code == 404
    hit = client.get("/_next/static/real.js")
    assert hit.status_code == 200 and "immutable" in hit.headers["cache-control"]
    miss = client.get("/_next/static/nope.js")
    assert miss.status_code == 404 and "immutable" not in miss.headers.get("cache-control", "")
