"""Bounded, read-only load probe. RATE and SECONDS are intentionally explicit."""
import concurrent.futures
import http.client
import json
import os
import threading
import time

HOST = "infomatt360.tecnomatt.com"
RATE = int(os.environ.get("PROBE_RATE", "10"))
SECONDS = int(os.environ.get("PROBE_SECONDS", "20"))
SOURCE = os.environ.get("PROBE_SOURCE", "unknown")
LOCAL = threading.local()


def connection():
    if not hasattr(LOCAL, "conn"):
        LOCAL.conn = http.client.HTTPSConnection(HOST, timeout=4)
    return LOCAL.conn


def probe(index):
    path = "/api/v1/health/ready" if index % 5 else "/"
    started = time.perf_counter()
    try:
        conn = connection()
        conn.request("GET", path, headers={"User-Agent": "InfoMatt360-controlled-load-probe/1"})
        response = conn.getresponse()
        response.read()
        return path, response.status, time.perf_counter() - started
    except Exception:
        if hasattr(LOCAL, "conn"):
            LOCAL.conn.close()
            del LOCAL.conn
        return path, 0, time.perf_counter() - started


def percentile(values, fraction):
    values = sorted(values)
    return round(values[min(len(values) - 1, int((len(values) - 1) * fraction))] * 1000)


def summarize(rows):
    durations = [row[2] for row in rows]
    status = {}
    for _, code, _ in rows:
        status[str(code)] = status.get(str(code), 0) + 1
    return {"requests": len(rows), "status": status, "p50_ms": percentile(durations, .5),
            "p95_ms": percentile(durations, .95), "p99_ms": percentile(durations, .99),
            "max_ms": round(max(durations) * 1000)}


def main():
    rows = []
    pending = []
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=48) as pool:
        for index in range(RATE * SECONDS):
            wait = start + index / RATE - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            pending.append(pool.submit(probe, index))
            if len(pending) > 60:
                rows.append(pending.pop(0).result())
        rows.extend(task.result() for task in pending)
    elapsed = time.perf_counter() - start
    out = {"source": SOURCE, "target_rps": RATE, "seconds": round(elapsed, 2),
           "actual_rps": round(len(rows) / elapsed, 2), **summarize(rows)}
    for path in ("/", "/api/v1/health/ready"):
        out[path] = summarize([row for row in rows if row[0] == path])
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
