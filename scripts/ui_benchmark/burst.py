"""Burst test: N users click at the same instant (N requests in flight, one connection each), the same method as
SIP's bench/burst.py, so the two products' numbers compare directly.

  page      the portal's HTML (/app/)
  book      a random wave's book (published file)
  crosstab  a random wave x question x pair of cuts (computed once, then cached)
  search    a random search term

    python burst.py http://nginx:8080 --mix book --users 1000,5000,10000
"""
import argparse, asyncio, random, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from user_mix import CUTS, Http, unzip

TERMS = ["inflation", "holiday", "grocery", "tariff", "gas prices", "spending", "glp", "amazon", "walmart", "income"]


def pct(values, q):
    values = sorted(values)
    return round(values[min(len(values) - 1, int(q * len(values)))] * 1000, 1) if values else None


def path_for(mix, rng, waves, questions):
    if mix == "page":
        return "/app/"
    wave = rng.choice(waves)
    if mix == "book":
        return f"/api/v1/waves/{wave}/book"
    if mix == "search":
        return f"/api/v1/search?q={rng.choice(TERMS).replace(' ', '+')}"
    a, b = rng.sample(CUTS, 2)
    return f"/api/v1/waves/{wave}/crosstab?q={rng.choice(questions[wave])}&by={a},{b}"


async def one(base, cookie, path, gate, latencies, errors):
    http = Http(base, cookie)
    await gate.wait()
    start = time.perf_counter()
    try:
        status, _, _ = await asyncio.wait_for(http.get(path), 120)
        (latencies if status == 200 else errors).append(time.perf_counter() - start if status == 200 else status)
    except Exception as e:
        errors.append(type(e).__name__)
    finally:
        if http.w:
            http.w.close()


async def main(a):
    http = Http(a.base)
    _, headers, _ = await http.get("/auth/dev-login?next=/")
    cookie = headers["set-cookie"].split(";")[0]
    http.cookie = cookie
    _, _, body = await http.get("/api/v1/waves")
    cuts = Path(a.published) / "api/v1/waves"
    waves = [w["survey_id"] for w in unzip(body) if (cuts / str(w["survey_id"]) / "cuts").is_dir()][: a.waves]
    questions = {w: [f.name.split(".")[0] for f in (cuts / str(w) / "cuts").iterdir()] for w in waves}
    rng = random.Random(a.seed)
    for n in map(int, a.users.split(",")):
        gate, latencies, errors = asyncio.Event(), [], []
        tasks = [asyncio.create_task(one(a.base, cookie, path_for(a.mix, rng, waves, questions), gate, latencies, errors))
                 for _ in range(n)]
        await asyncio.sleep(0.5)
        start = time.perf_counter()
        gate.set()
        await asyncio.gather(*tasks)
        took = time.perf_counter() - start
        kinds = {e: errors.count(e) for e in set(errors)}
        print(f"{a.mix:9} users={n:6} all_done={took:6.2f}s rps={n / took:7.0f} p50={pct(latencies, .5)}ms "
              f"p95={pct(latencies, .95)}ms p99={pct(latencies, .99)}ms errors={len(errors)} {kinds or ''}", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("base")
    p.add_argument("--mix", choices=["page", "book", "crosstab", "search"], default="book")
    p.add_argument("--users", default="1000,5000,10000")
    p.add_argument("--waves", type=int, default=40, help="the newest N waves to pick from")
    p.add_argument("--published", default="data/published/current", help="the published folder: which questions have cut tables")
    p.add_argument("--seed", type=int, default=1)
    asyncio.run(main(p.parse_args()))
