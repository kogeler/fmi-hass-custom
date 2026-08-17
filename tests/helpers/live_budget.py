# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Cross-process request budget for parallel live FMI probes."""

from __future__ import annotations

import asyncio
import fcntl
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

MAX_LIVE_REQUESTS = 10
MAX_CONCURRENT_REQUESTS = 2


class LiveBudgetExceeded(RuntimeError):
    """Raised before a request would exceed the suite-wide live budget."""


class LiveRequestBudget:
    """Coordinate a bounded request counter and semaphore across xdist workers."""

    def __init__(
        self,
        root: Path,
        *,
        maximum: int = MAX_LIVE_REQUESTS,
        concurrency: int = MAX_CONCURRENT_REQUESTS,
    ) -> None:
        if maximum < 1 or concurrency < 1:
            raise ValueError("live request limits must be positive")
        self._root = root
        self._maximum = maximum
        self._concurrency = concurrency

    def _reserve(self) -> int:
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        counter = self._root / "requests"
        with counter.open("a+", encoding="ascii") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.seek(0)
            raw = stream.read().strip()
            current = int(raw) if raw else 0
            if current >= self._maximum:
                raise LiveBudgetExceeded(
                    f"live FMI request budget exhausted at {self._maximum} attempts"
                )
            current += 1
            stream.seek(0)
            stream.truncate()
            stream.write(f"{current}\n")
            stream.flush()
            return current

    def _acquire_slot(self) -> int:
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            for index in range(self._concurrency):
                descriptor = os.open(
                    self._root / f"slot-{index}",
                    os.O_CREAT | os.O_RDWR,
                    0o600,
                )
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    os.close(descriptor)
                    continue
                return descriptor
            time.sleep(0.01)
        raise LiveBudgetExceeded("timed out waiting for a live FMI request slot")

    @asynccontextmanager
    async def request(self) -> AsyncIterator[int]:
        """Reserve one global attempt and one bounded concurrent request slot."""
        descriptor = await asyncio.to_thread(self._acquire_slot)
        try:
            attempt = await asyncio.to_thread(self._reserve)
            yield attempt
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
