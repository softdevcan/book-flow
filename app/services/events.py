"""In-process pub/sub event bus for SSE streaming.

One asyncio.Queue per active subscriber, keyed by book_id.
`publish` is thread-safe so background translation tasks can call it.
Each queue is capped at 100 items; oldest are dropped on overflow.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# book_id -> list[asyncio.Queue]
# All access happens on the single asyncio event loop, so no lock needed.
_subscribers: dict[int, list[asyncio.Queue]] = defaultdict(list)

# Max queued events per subscriber before oldest are dropped.
_QUEUE_MAXSIZE = 100


def subscribe(book_id: int) -> asyncio.Queue:
    """Register a new subscriber and return its queue.

    Sync: a plain list append doesn't need the GIL released. Called from the
    SSE endpoint, which is already on the event loop.
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    _subscribers[book_id].append(q)
    logger.debug("events: subscriber added for book %s (total=%d)", book_id, len(_subscribers[book_id]))
    return q


def unsubscribe(book_id: int, q: asyncio.Queue) -> None:
    """Remove a subscriber queue."""
    try:
        _subscribers[book_id].remove(q)
    except (ValueError, KeyError):
        pass
    if book_id in _subscribers and not _subscribers[book_id]:
        del _subscribers[book_id]
    logger.debug("events: subscriber removed for book %s", book_id)


def publish(book_id: int, event: dict[str, Any]) -> None:
    """Enqueue `event` to all subscribers of `book_id`.

    Called from async code running on the event loop (translator background
    tasks, request handlers). `put_nowait` is sync and safe here.
    Drops the oldest item when a queue is full so a slow client can't OOM.
    """
    queues = list(_subscribers.get(book_id, []))
    for q in queues:
        if q.full():
            try:
                q.get_nowait()  # drop oldest
            except asyncio.QueueEmpty:
                pass
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass  # race — safe to skip
