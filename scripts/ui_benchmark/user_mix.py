"""Simultaneous portal users against one server. Every simulated user runs the real screens' requests in a loop
with think time between clicks:

  open the library (/waves) → open a wave (/book: 70 % one of the last 8 weeks, 30 % any archive wave, so the
  cache misses) → most visits then open a cross-tab with two cuts (/crosstab), a trend (/trend) or a search.

Steps through user counts; each step ramps up, then measures. Reports per endpoint: requests/s, p50/p95/p99 and
errors, plus each step's measuring window (epoch seconds) so server CPU/memory samples taken outside the loader
(docker stats on the host, see docker_stats.sh) can be matched to it. One keep-alive connection per user.

    python user_mix.py http://cip-api:8000 --users 100,500,1000,2000 --think 10 --seconds 60
"""
import argparse, asyncio, gzip, json, random, statistics, time
from collections import defaultdict
from urllib.parse import quote, urlsplit

CUTS = ["gender", "age_band", "generation", "income_band", "census_region", "urbanicity"]
unzip = lambda body: json.loads(gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body)   # browsers ask for gzip; so do we


class Http:
    """A minimal HTTP/1.1 keep-alive client: one per user, like one browser tab."""
    def __init__(self, base, cookie=""):
        u = urlsplit(base)
        self.host, self.port, self.cookie, self.r, self.w = u.hostname, u.port or 80, cookie, None, None

    async def get(self, path):
        for attempt in range(2):
            try:
                if self.w is None:
                    self.r, self.w = await asyncio.open_connection(self.host, self.port, limit=2**24)
                self.w.write(f"GET {path} HTTP/1.1\r\nHost: {self.host}\r\nCookie: {self.cookie}\r\nAccept-Encoding: gzip\r\n"
                             f"Connection: keep-alive\r\n\r\n".encode())
                status = await self.r.readline()
                if not status:
                    raise ConnectionError("closed")
                headers = {}
                while (line := await self.r.readline()) not in (b"\r\n", b""):
                    k, _, v = line.decode().partition(":")
                    headers[k.strip().lower()] = v.strip()
                body = await self.r.readexactly(int(headers.get("content-length", 0)))
                return int(status.split()[1]), headers, body
            except (ConnectionError, asyncio.IncompleteReadError, OSError):
                if self.w:
                    self.w.close()
                self.w = None
                if attempt:
                    raise


class Stats:
    def __init__(self):
        self.lat, self.errors, self.done = defaultdict(list), defaultdict(int), 0

    def add(self, kind, ms, ok):
        self.lat[kind].append(ms)
        self.done += 1
        if not ok:
            self.errors[kind] += 1


async def user(base, cookie, waves, recent, think, stop, stats, measuring, books):
    http = Http(base, cookie)
    await asyncio.sleep(random.random() * think)   # users arrive spread out, not all at once

    async def call(kind, path):
        start = time.perf_counter()
        try:
            status, _, body = await http.get(path)
            ok = status == 200
        except Exception:
            status, body, ok = 0, b"", False
        if measuring():
            stats.add(kind, (time.perf_counter() - start) * 1000, ok)
        return body if ok else None

    while time.time() < stop:
        await call("waves", "/api/v1/waves")
        await asyncio.sleep(random.expovariate(1 / think))
        wave = random.choice(recent) if random.random() < 0.7 else random.choice(waves)
        body = await call("book", f"/api/v1/waves/{wave}/book")
        if wave not in books and body:
            books[wave] = [q["id"] for q in unzip(body)["questions"]]
        qs = books.get(wave) or []
        for _ in range(random.randint(1, 3)):   # a few more clicks in this wave
            await asyncio.sleep(random.expovariate(1 / think))
            if time.time() >= stop or not qs:
                break
            q, roll = quote(random.choice(qs)), random.random()
            if roll < 0.45:
                a, b = random.sample(CUTS, 2)
                await call("crosstab", f"/api/v1/waves/{wave}/crosstab?q={q}&by={a},{b}&weeks={random.choice([1, 1, 4])}")
            elif roll < 0.85:
                await call("trend", f"/api/v1/trend?survey_id={wave}&q={q}")
            else:
                await call("search", f"/api/v1/search?q={quote(random.choice(['holiday', 'amazon', 'gas', 'grocery', 'ai tools', 'walmart', 'income', 'denim']))}")
        await asyncio.sleep(random.expovariate(1 / think))


async def step(a, n, cookie, waves, recent, books):
    stats, start = Stats(), time.time()
    measure_from = start + a.ramp
    stop = measure_from + a.seconds
    await asyncio.gather(*[user(a.base, cookie, waves, recent, a.think, stop, stats, lambda: measure_from <= time.time() < stop, books)
                           for _ in range(n)])
    took = a.seconds   # only requests that started inside the window are counted
    every = [ms for v in stats.lat.values() for ms in v]
    pick = lambda v, q: sorted(v)[min(len(v) - 1, int(q * len(v)))] if v else float("nan")
    print(f"\n== {n} users (think {a.think}s): {stats.done / took:,.0f} req/s · p50 {statistics.median(every):.1f} ms · p95 {pick(every, .95):.1f} ms"
          f" · p99 {pick(every, .99):.1f} ms · errors {sum(stats.errors.values())} · window {measure_from:.0f}-{measure_from + took:.0f}", flush=True)
    for kind in ("waves", "book", "crosstab", "trend", "search"):
        v = stats.lat.get(kind, [])
        if v:
            print(f"   {kind:<9} {len(v) / took:8.1f} req/s  p50 {statistics.median(v):7.1f}  p95 {pick(v, .95):7.1f}  p99 {pick(v, .99):7.1f} ms"
                  f"  errors {stats.errors[kind]}", flush=True)


async def main(a):
    http = Http(a.base)
    _, headers, _ = await http.get("/auth/dev-login?next=/")
    cookie = headers["set-cookie"].split(";")[0]
    http.cookie = cookie
    _, _, body = await http.get("/api/v1/waves")
    rows = unzip(body)
    waves = [w["survey_id"] for w in rows]
    recent = [w["survey_id"] for w in rows if w["study_type"] == "tracker"][:8]
    print(f"{len(waves)} waves, recent tracker waves {recent}", flush=True)
    books = {}
    for n in [int(x) for x in a.users.split(",")]:
        await step(a, n, cookie, waves, recent, books)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("base")
    p.add_argument("--users", default="100,500,1000")
    p.add_argument("--think", type=float, default=10.0, help="mean seconds between a user's clicks")
    p.add_argument("--seconds", type=int, default=60)
    p.add_argument("--ramp", type=int, default=20)
    asyncio.run(main(p.parse_args()))
