import asyncio
from typing import Optional


class Limiter:
    def __init__(self, max_interval: float):
        self.max_interval = max_interval
        self._last_call_time: Optional[float] = None

    async def __call__(self):
        loop = asyncio.get_event_loop()

        if self._last_call_time is not None:
            wait_time = self.max_interval - (loop.time() - self._last_call_time)

            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self._last_call_time = loop.time()
