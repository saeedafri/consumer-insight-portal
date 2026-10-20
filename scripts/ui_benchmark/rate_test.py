"""Open-loop load test: send requests at a fixed rate and time each one from when it was SCHEDULED,
so queueing delay counts (no coordinated omission). This is how real users behave: they keep arriving
whether or not the server is keeping up.

    python scripts/ui_benchmark/rate_test.py URL --cookie "cip_session=..." --rates 500,1000,2000 --seconds 20
"""
import argparse, asyncio, statistics, time
from urllib.parse import urlsplit


async def connection(host, port, request, queue, results):
    reader, writer = await asyncio.open_connection(host, port)   # opened up front, gradually (see run)
    while True:
        due = await queue.get()
        if due is None:
            break
        for _ in range(2):   # a keep-alive connection the server closed while idle is reopened once
            if writer is None:
                reader, writer = await asyncio.open_connection(host, port)
            writer.write(request)
            status = await reader.readline()
            if status:
                break
            writer.close()
            writer = None
        length = 0
        while (line := await reader.readline()) not in (b"\r\n", b""):
            if line.lower().startswith(b"content-length:"):
                length = int(line.split(b":")[1])
        await reader.readexactly(length)
        results.append((time.perf_counter() - due, status.split()[1:2] == [b"200"]))
    if writer:
        writer.close()


async def run(url, cookie, rate, seconds, connections):
    u = urlsplit(url)
    request = (f"GET {u.path}{'?' + u.query if u.query else ''} HTTP/1.1\r\nHost: {u.hostname}\r\nCookie: {cookie}\r\n"
               f"Accept-Encoding: gzip\r\nConnection: keep-alive\r\n\r\n").encode()
    queue, results = asyncio.Queue(), []
    workers = []
    for _ in range(connections):   # open gradually: the macOS listen backlog is only 128
        workers.append(asyncio.create_task(connection(u.hostname, u.port, request, queue, results)))
        await asyncio.sleep(0.005)
    start, total = time.perf_counter(), rate * seconds
    for i in range(total):
        due = start + i / rate
        await asyncio.sleep(max(0, due - time.perf_counter()))
        queue.put_nowait(due)
    for _ in workers:
        queue.put_nowait(None)
    await asyncio.gather(*workers)
    lat = sorted(r[0] * 1000 for r in results)
    ok = sum(r[1] for r in results)
    pick = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))]
    print(f"rate={rate:>5}/s  done={len(results)} ok={ok}  achieved={len(results) / (time.perf_counter() - start):.0f}/s  "
          f"p50={statistics.median(lat):.1f}ms p95={pick(.95):.1f}ms p99={pick(.99):.1f}ms max={lat[-1]:.1f}ms", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--cookie", required=True)
    p.add_argument("--rates", default="500,1000,2000")
    p.add_argument("--seconds", type=int, default=20)
    p.add_argument("--connections", type=int, default=200)
    a = p.parse_args()
    for r in (int(x) for x in a.rates.split(",")):
        asyncio.run(run(a.url, a.cookie, r, a.seconds, a.connections))
