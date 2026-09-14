"""Print size/timing only; never print captured request/response content.

Run: python -m src.tests.benchmark_context_index /path/events.jsonl session-id
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from src.server.context import ContextEventStream
from src.server.context_index import ContextIndex


async def main():
    start = time.perf_counter()
    index = ContextIndex(ContextEventStream(Path(sys.argv[1]), sys.argv[2]))
    try:
        await index.ready.wait()
        cold = time.perf_counter() - start
        start = time.perf_counter()
        snapshot = index.snapshot()
        encoded = json.dumps(snapshot)
        warm = time.perf_counter() - start
        full = sum(len(json.dumps(event)) for event in index.full.values())
        print(json.dumps({"requests": snapshot["total"], "cold_index_seconds": round(cold, 3),
                          "warm_snapshot_ms": round(warm * 1000, 2), "initial_characters": len(encoded),
                          "full_replay_characters": full, "reduction_percent": round(100 * (1 - len(encoded) / full), 2)}))
    finally:
        await index.close()


if __name__ == "__main__":
    asyncio.run(main())
