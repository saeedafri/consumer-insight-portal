"""Time every portal API endpoint against a running server: the first (cold) call and the warm p50/p95 of 10 more.
Exits 1 when a warm p95 is over its budget. Read-only; signs in with the local dev login.

    python scripts/api_timing.py http://127.0.0.1:8000 --wave 415
    python scripts/api_timing.py https://<tunnel>.trycloudflare.com --wave 415 --budget 400   # includes the internet
"""
import argparse
import gzip
import http.cookiejar
import json
import statistics
import sys
import time
import urllib.request
from urllib.parse import quote


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("base")
    p.add_argument("--wave", type=int, default=415)
    p.add_argument("--budget", type=float, default=50, help="warm p95 budget per endpoint, ms")
    a = p.parse_args()
    jar = http.cookiejar.CookieJar()
    web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    web.open(f"{a.base}/auth/dev-login?next=/").read()

    def get(path):
        request = urllib.request.Request(a.base + path, headers={"Accept-Encoding": "gzip"})
        start = time.perf_counter()
        with web.open(request) as r:
            body = r.read()
            ms = 1000 * (time.perf_counter() - start)
            return ms, len(body), json.loads(gzip.decompress(body) if r.headers.get("Content-Encoding") == "gzip" else body)

    _, _, book = get(f"/api/v1/waves/{a.wave}/book")
    w = book["wave"]
    family = f"{quote(w['survey_family'])}/{w['study_type']}"
    picks = [q["id"] for q in book["questions"][:3]]
    urls = ["/api/v1/waves", f"/api/v1/waves/{a.wave}/book", "/api/v1/schedule", "/api/v1/search?q=holiday%20shopping",
            *[f"/api/v1/questions/{family}/{quote(q)}" for q in picks],
            *[f"/api/v1/waves/{a.wave}/crosstab?q={quote(q)}&by=gender,generation&weeks=1" for q in picks[:2]],
            f"/api/v1/waves/{a.wave}/crosstab?q={quote(picks[0])}&by=income_band,census_region&weeks=4",
            f"/api/v1/waves/{a.wave}/results?q={quote(picks[0])}&dim=total,gender"]
    over = 0
    print(f"{'endpoint':78} {'cold ms':>8} {'p50 ms':>7} {'p95 ms':>7} {'KB':>6}")
    for url in urls:
        cold, size, _ = get(url)
        warm = sorted(get(url)[0] for _ in range(10))
        p95 = warm[9]
        flag = "" if p95 <= a.budget else "  OVER BUDGET"
        over += bool(flag)
        print(f"{url[:78]:78} {cold:8.1f} {statistics.median(warm):7.1f} {p95:7.1f} {size / 1024:6.1f}{flag}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
