"""Exercise the Ravan MCP HTTP surface for a bounded soak interval.

This intentionally uses the public MCP client protocol instead of internal
imports, so it catches transport, lifespan, and tool-registration regressions
in the same path external agents use.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


@dataclass
class Results:
    calls: int = 0
    errors: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)

    def merge(self, other: "Results") -> None:
        self.calls += other.calls
        self.errors += other.errors
        self.latencies_ms.extend(other.latencies_ms)
        if not self.tools:
            self.tools = other.tools


async def worker(url: str, site_id: str, duration: float, calls_per_second: float) -> Results:
    result = Results()
    interval = 1.0 / max(calls_per_second, 0.01)
    deadline = time.monotonic() + duration
    async with streamable_http_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            result.tools = [tool.name for tool in listed.tools]
            while time.monotonic() < deadline:
                started = time.perf_counter()
                try:
                    response = await session.call_tool("sources_list", {"site_id": site_id})
                    if getattr(response, "is_error", False):
                        result.errors += 1
                    else:
                        result.calls += 1
                except Exception:
                    result.errors += 1
                result.latencies_ms.append((time.perf_counter() - started) * 1000)
                await asyncio.sleep(max(0.0, interval - (time.perf_counter() - started)))
    return result


async def run(args: argparse.Namespace) -> dict[str, object]:
    started = time.monotonic()
    workers = await asyncio.gather(
        *[
            worker(args.url, args.site_id, args.seconds, args.calls_per_second)
            for _ in range(args.sessions)
        ]
    )
    total = Results()
    for item in workers:
        total.merge(item)
    elapsed = time.monotonic() - started
    ordered = sorted(total.latencies_ms)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] if ordered else None
    return {
        "url": args.url,
        "duration_seconds": round(elapsed, 2),
        "sessions": args.sessions,
        "calls": total.calls,
        "errors": total.errors,
        "tool_count": len(total.tools),
        "tools": total.tools,
        "latency_ms": {
            "p50": round(statistics.median(total.latencies_ms), 2) if total.latencies_ms else None,
            "p95": round(p95, 2) if p95 is not None else None,
            "max": round(max(total.latencies_ms), 2) if total.latencies_ms else None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8020/mcp/")
    parser.add_argument("--site-id", default="demo-site")
    parser.add_argument("--seconds", type=float, default=900)
    parser.add_argument("--sessions", type=int, default=4)
    parser.add_argument("--calls-per-second", type=float, default=4)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), indent=2))


if __name__ == "__main__":
    main()
