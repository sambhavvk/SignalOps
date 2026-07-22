import asyncio
import os

import httpx


async def main() -> None:
    base = os.getenv("SIGNALOPS_API_URL", "http://signalops-api:8000/api/v1")
    interval = max(5, int(os.getenv("DETECTOR_INTERVAL_SECONDS", "20")))
    async with httpx.AsyncClient(timeout=5) as client:
        while True:
            try:
                await client.post(f"{base}/detector/evaluate")
            except httpx.HTTPError:
                pass
            await asyncio.sleep(interval)


asyncio.run(main())
