import asyncio
import os
import random
from uuid import uuid4

import httpx


async def main() -> None:
    random.seed(int(os.getenv("TRAFFIC_SEED", "20260721")))
    base = os.getenv("ORDERS_URL", "http://orders-api:8080")
    interval = float(os.getenv("TRAFFIC_INTERVAL_SECONDS", "2"))
    async with httpx.AsyncClient(timeout=5) as client:
        while True:
            key = f"traffic-{uuid4()}"
            try:
                await client.post(
                    f"{base}/api/v1/orders",
                    headers={"Idempotency-Key": key, "X-Correlation-ID": key},
                    json={"productId": "sku-signal-lamp", "quantity": random.choice([1, 1, 1, 2]), "amount": 49.0},
                )
            except httpx.HTTPError:
                pass
            await asyncio.sleep(interval)


asyncio.run(main())
