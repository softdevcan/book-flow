"""SSE endpoint: GET /api/books/{book_id}/events

Streams chunk state changes to the browser via Server-Sent Events.
One stream per open book tab; backend emits events whenever a chunk
changes state (translated, failed, batch progress).

If the stream disconnects the frontend reconnects automatically and
falls back to the existing 3-second poll.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.services import events as bus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


@router.get("/api/books/{book_id}/events")
async def chunk_events(book_id: int, request: Request):
    """Open an SSE stream for a book. Emits chunk_updated, chunk_failed,
    batch_progress events. Sends a keep-alive ping every 15 s."""
    q = bus.subscribe(book_id)
    logger.info("events: SSE stream opened for book %s", book_id)

    async def gen():
        try:
            # Immediate handshake so the client knows the stream is live.
            yield {"event": "ready", "data": "{}"}
            while True:
                if await request.is_disconnected():
                    logger.info("events: client disconnected for book %s", book_id)
                    return
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield {"event": event["type"], "data": json.dumps(event)}
                except asyncio.TimeoutError:
                    # Keep-alive ping to prevent proxy/browser from closing the stream.
                    yield {"event": "ping", "data": "{}"}
        finally:
            bus.unsubscribe(book_id, q)
            logger.info("events: SSE stream closed for book %s", book_id)

    return EventSourceResponse(gen())
