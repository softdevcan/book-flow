# Plan: UX & Realtime Upgrade Pass

## Context

BookFlow now ships multilingual translation, two-stage pipeline, and version history. The interaction surface, though, is still bare:

- Background translations finish silently — no toast, no banner. Reviewers must stare at the page to know when chunks land.
- The UI polls `GET /api/books/{id}/chunks` every 3 s while any chunk is `raw`+no-translation ([BookDetail.tsx:113-122](../frontend/src/components/BookDetail.tsx#L113-L122)). That's a wasteful round-trip every 3 seconds per open tab, and it doesn't push intermediate state (stage 1 done, model loading, etc.).
- There's no way to filter chunks (e.g. "show only failed", "show only in_review") — the chapter sidebar is the only navigation.
- Translation versions are listed in [ChunkCard.tsx:189-224](../frontend/src/components/ChunkCard.tsx#L189-L224) but you can't *compare* a Builder draft against an Artist refinement except by mentally diffing two paragraphs.
- No dark mode. Reviewers work in literary tools at night.
- No keyboard shortcuts — translating 100+ chunks per book is a mousing marathon.

This PR adds a coherent UX layer on top of the existing structure without disrupting any of it:
**toasts + sticky progress bar + chunk filter/search + version diff modal + SSE realtime + dark mode + keyboard shortcuts.**

No auth, no backend schema changes, no provider changes. The only backend addition is one SSE endpoint that streams chunk-state changes for an open book.

---

## Decisions

- **Toast lib**: `sonner` (~3 kb, accessible, stacking, promise toasts). Mounted once in [main.tsx](../frontend/src/main.tsx) so any component can call `toast.success(...)` / `toast.error(...)`.
- **Diff style**: inline word-level diff. Library: `diff` (~5 kb). Removed = red strikethrough; added = green underline; unchanged flows naturally. Reads like prose, not a code review.
- **Realtime**: Server-Sent Events. One stream per book: `GET /api/books/{id}/events`. Backend emits `{type, chunk_id, status, ...}` whenever a chunk changes state. Frontend keeps the existing 3 s polling as a fallback if the stream disconnects.
- **Dark mode**: Tailwind `class` strategy. State persisted to `localStorage` with `prefers-color-scheme` as the initial default. Single `ThemeToggle` button in the header.
- **Keyboard shortcuts**: vanilla `keydown` listener, no library. Active only when a chunk view is rendered and no input is focused.

---

## Architecture overview

```
┌────────────────────────────────────────────────────────────────┐
│ Frontend                                                       │
│                                                                │
│   <Toaster />        ←── global, mounted in main.tsx           │
│   <ThemeProvider>    ←── dark mode wrapper                     │
│   <App>                                                        │
│     ├── <Header> ……………………………………………… [ThemeToggle]              │
│     ├── <BookList> ─── notify on upload/delete success         │
│     └── <BookDetail>                                           │
│         ├── <BatchProgressBar />   ← sticky, derived from chunks│
│         ├── <ChunkFilterBar />     ← status/text/failed filter │
│         ├── <ChunkCard>                                        │
│         │   ├── translate → toast.promise(...)                 │
│         │   └── <VersionDiffModal />  ← inline word-level diff │
│         └── useChunkEvents(bookId) ── SSE hook, fallback poll  │
│         └── useChunkKeybindings()  ── j/k/t/a/e/  shortcuts    │
└────────────────────────────────────────────────────────────────┘
                              ▲
                              │ EventSource
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ Backend                                                        │
│                                                                │
│   GET /api/books/{id}/events   ← sse-starlette, in-process bus │
│                                                                │
│   translator._persist_translation ── emits "chunk_updated"     │
│   translator._mark_failed         ── emits "chunk_failed"      │
│   chunks.update_chunk             ── emits "chunk_updated"     │
└────────────────────────────────────────────────────────────────┘
```

The event bus is a per-process `asyncio` pub/sub (one `asyncio.Queue` per active subscriber, dispatched by book_id). No Redis, no schema change. If the backend restarts, frontend reconnects automatically.

---

## Backend changes

### 1. New dependency
[requirements.txt](../requirements.txt): add `sse-starlette>=2.1`.

### 2. New event bus — `app/services/events.py` (new file)

A tiny in-process pub/sub keyed by `book_id`. One `asyncio.Queue` per subscriber. `publish` is thread-safe (`loop.call_soon_threadsafe`) so the translator background tasks can call it. Each queue is capped at ~100 items; oldest are dropped on overflow so a slow client can't OOM the backend.

Event shape (intentionally small — frontend re-fetches the chunk on demand):
```json
{ "type": "chunk_updated", "chunk_id": 42, "status": "in_review", "translated": true, "failed": false }
{ "type": "chunk_failed",  "chunk_id": 42, "reason": "stage1_failed: ..." }
{ "type": "batch_progress", "phase": "stage1" | "stage2", "done": 7, "total": 45 }
```

### 3. New endpoint — `app/api/endpoints/events.py` (new file)

```python
@router.get("/api/books/{book_id}/events")
async def chunk_events(book_id: int, request: Request):
    q = bus.subscribe(book_id)
    async def gen():
        try:
            yield {"event": "ready", "data": "{}"}
            while True:
                if await request.is_disconnected(): return
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield {"event": event["type"], "data": json.dumps(event)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}   # keep-alive
        finally:
            bus.unsubscribe(book_id, q)
    return EventSourceResponse(gen())
```

Mount in [main.py](../main.py) alongside existing routers.

### 4. Wire publishers into translator — [app/services/translator.py](../app/services/translator.py)

Three call sites need to publish:
- [_persist_translation](../app/services/translator.py#L123) — after commit, publish `chunk_updated` with `chunk.id`, `status`, `translated=True`.
- [_mark_failed](../app/services/translator.py#L267) — after commit, publish `chunk_failed`.
- [translate_book_batched](../app/services/translator.py#L300) — at the start of each phase loop and after each chunk persist, publish `batch_progress` with `done/total/phase`.

The chunk's `book_id` is available on the loaded `Chunk` (or passed in). For `_mark_failed`, fetch `chunk.book_id` before commit.

Also publish from [chunks.update_chunk](../app/api/endpoints/chunks.py#L115) so manual edits propagate to other open tabs.

### 5. nginx + Vite SSE compatibility

[frontend/nginx.conf:16-24](../frontend/nginx.conf#L16-L24): add SSE-friendly settings inside `location /api/`:
```
proxy_buffering off;
proxy_cache off;
proxy_set_header Connection '';
proxy_http_version 1.1;
chunked_transfer_encoding off;
```
Vite dev proxy already supports SSE through `/api` without extra config.

---

## Frontend changes

### 6. Dependencies — [frontend/package.json](../frontend/package.json)

Add to `dependencies`:
- `sonner` (toasts)
- `diff` (word-level diff)
- `@types/diff` to `devDependencies`

### 7. Toaster mount — [frontend/src/main.tsx](../frontend/src/main.tsx)

Wrap the app:
```tsx
<React.StrictMode>
  <ThemeProvider>
    <Toaster richColors closeButton position="bottom-right" />
    <App />
  </ThemeProvider>
</React.StrictMode>
```

### 8. Theme (dark mode)

- [tailwind.config.js](../frontend/tailwind.config.js): add `darkMode: "class"`.
- New `frontend/src/theme.tsx`: `ThemeProvider` + `useTheme` hook. Reads `localStorage.theme` ("light" | "dark"), falls back to `matchMedia('(prefers-color-scheme: dark)')`. Toggles `document.documentElement.classList` between `light` / `dark`. Persists on change.
- New `frontend/src/components/ThemeToggle.tsx`: sun/moon SVG button in [App.tsx](../frontend/src/App.tsx) header.
- Component pass: convert hardcoded `bg-white`, `text-slate-500`, `border-slate-200`, `bg-slate-50` etc. across [App.tsx](../frontend/src/App.tsx), [BookList.tsx](../frontend/src/components/BookList.tsx), [BookDetail.tsx](../frontend/src/components/BookDetail.tsx), [ChunkCard.tsx](../frontend/src/components/ChunkCard.tsx), [GlossaryPanel.tsx](../frontend/src/components/GlossaryPanel.tsx), [UploadForm.tsx](../frontend/src/components/UploadForm.tsx), [ModelPicker.tsx](../frontend/src/components/ModelPicker.tsx), [AnalyticsPage.tsx](../frontend/src/components/AnalyticsPage.tsx) to pair each with a `dark:` variant (e.g. `bg-white dark:bg-slate-900`). One mechanical pass; no logic changes.

### 9. SSE hook — `frontend/src/hooks/useChunkEvents.ts` (new)

```ts
export function useChunkEvents(bookId: number, onChange: (e: ChunkEvent) => void) {
  useEffect(() => {
    const es = new EventSource(`/api/books/${bookId}/events`);
    const handlers = ["chunk_updated", "chunk_failed", "batch_progress"];
    handlers.forEach((t) => es.addEventListener(t, (ev) =>
      onChange({ type: t, ...JSON.parse((ev as MessageEvent).data) })
    ));
    return () => es.close();
  }, [bookId, onChange]);
}
```

[BookDetail.tsx](../frontend/src/components/BookDetail.tsx) consumes the hook: each event triggers a targeted `api.getChunk(id)` and replaces that chunk in state (re-uses existing `replaceChunk`). The 3-second polling stays as a fallback (kicks in only when `EventSource.readyState === CLOSED` and a chunk is still pending).

### 10. Toast wiring

- Upload success/error: `toast.success("Uploaded ‘…’ — 45 chunks ready")` in [UploadForm.tsx](../frontend/src/components/UploadForm.tsx). Existing inline banner remains for permanent confirmation; toasts are ephemeral.
- Translate queued: `toast.promise(api.translateChunk(...), { loading: "Queuing…", success: "Queued #7", error: "Queue failed" })` in [BookDetail.tsx](../frontend/src/components/BookDetail.tsx).
- SSE-driven: in `useChunkEvents` callback, fire `toast.success("#7 translated")` for `chunk_updated`+`translated:true`, `toast.error("#7 failed — …")` for `chunk_failed`. Coalesce: if >5 events arrive within 2 s, collapse to one `toast.success("12 chunks translated")` to avoid spam during book-level batches.

### 11. Sticky batch progress bar — `frontend/src/components/BatchProgressBar.tsx` (new)

Sticky top bar shown while any chunk is `raw` with no translation OR a `batch_progress` event arrived in the last 30 s. Derived purely from local state:
- `translated / total` count.
- Stage chip if a recent `batch_progress` event exists: `Stage 1 · 7/45` or `Stage 2 · 3/45`.
- Slim animated indigo bar identical to the existing one in [BookDetail.tsx:243-249](../frontend/src/components/BookDetail.tsx#L243-L249), pinned to top of viewport via `position: sticky; top: 0` + `z-30`.

Replaces the inline progress strip in BookDetail for one source of truth.

### 12. Chunk filter bar — `frontend/src/components/ChunkFilterBar.tsx` (new)

Above the chapter content area in [BookDetail.tsx](../frontend/src/components/BookDetail.tsx):
- Status chips: All · Raw · In review · Approved · Failed (multi-select, OR within group).
- Text search: case-insensitive substring match on `source_text` OR `translated_text`.
- Failed-only toggle (shortcut to filter on chunks whose notes start with `translation_failed` / `stage1_failed` / `stage2_failed`).

State held in `BookDetail`; applied as `activeGroup.chunks.filter(...)`. Counts on chips reflect total in chapter (not the current filter), so they remain navigational.

### 13. Version diff modal — `frontend/src/components/VersionDiffModal.tsx` (new)

In [ChunkCard.tsx](../frontend/src/components/ChunkCard.tsx) versions list ([lines 189-224](../frontend/src/components/ChunkCard.tsx#L189-L224)), each non-active version gets a "Compare to active" button. Modal renders:
- Top: metadata strip (pipeline · models · timestamp) for both versions.
- Body: word-level diff using `diff.diffWordsWithSpace(activeText, otherText)`. Removed words wrapped `<del className="bg-red-100 dark:bg-red-900/40 line-through">`, added `<ins className="bg-emerald-100 dark:bg-emerald-900/40 no-underline">`. Whitespace preserved.
- Footer: "Use this version" button (re-uses existing `api.activateVersion`).

Modal is a portal-mounted `<div role="dialog">` with Esc-to-close and click-outside-to-close. No router/lib needed.

### 14. Keyboard shortcuts — `frontend/src/hooks/useChunkKeybindings.ts` (new)

Active only when `activeView === "chunks"` and no `<input>`/`<textarea>`/`[contenteditable]` is focused. Bindings:
- `j` / `k` — next / prev chunk (smooth-scroll into view, set `data-active` for visual ring).
- `t` — translate focused chunk (calls the existing `translateOne` path).
- `a` — approve focused chunk (sets status approved via existing `updateChunk`).
- `e` — focus the chunk's edit textarea (opens the existing edit mode in ChunkCard).
- `/` — focus the filter bar's search input.
- `?` — open a tiny help overlay listing the shortcuts.

`BookDetail` tracks `focusedChunkId` in state and passes it down so `ChunkCard` can render the focus ring. ChunkCard exposes `data-chunk-id` on its `<article>` for scroll-into-view.

---

## Critical files

- New: `app/services/events.py`
- New: `app/api/endpoints/events.py`
- Edit: [app/services/translator.py](../app/services/translator.py) — publish at `_persist_translation`, `_mark_failed`, batch progress
- Edit: [app/api/endpoints/chunks.py](../app/api/endpoints/chunks.py) — publish in `update_chunk`
- Edit: [main.py](../main.py) — mount events router
- Edit: [requirements.txt](../requirements.txt) — `sse-starlette`
- Edit: [frontend/package.json](../frontend/package.json) — `sonner`, `diff`, `@types/diff`
- Edit: [frontend/tailwind.config.js](../frontend/tailwind.config.js) — `darkMode: "class"`
- New: `frontend/src/theme.tsx`
- New: `frontend/src/hooks/useChunkEvents.ts`
- New: `frontend/src/hooks/useChunkKeybindings.ts`
- New: `frontend/src/components/ThemeToggle.tsx`
- New: `frontend/src/components/BatchProgressBar.tsx`
- New: `frontend/src/components/ChunkFilterBar.tsx`
- New: `frontend/src/components/VersionDiffModal.tsx`
- Edit: [frontend/src/main.tsx](../frontend/src/main.tsx) — mount Toaster + ThemeProvider
- Edit: [frontend/src/App.tsx](../frontend/src/App.tsx) — header gets ThemeToggle; dark variants
- Edit: [frontend/src/components/BookDetail.tsx](../frontend/src/components/BookDetail.tsx) — SSE hook, filter bar, batch progress, focus state, keybindings
- Edit: [frontend/src/components/ChunkCard.tsx](../frontend/src/components/ChunkCard.tsx) — focus ring, data-chunk-id, "Compare" buttons, dark variants
- Edit: [frontend/src/components/UploadForm.tsx](../frontend/src/components/UploadForm.tsx) — toast on success/error
- Edit: [frontend/src/components/BookList.tsx](../frontend/src/components/BookList.tsx), [GlossaryPanel.tsx](../frontend/src/components/GlossaryPanel.tsx), [ModelPicker.tsx](../frontend/src/components/ModelPicker.tsx), [AnalyticsPage.tsx](../frontend/src/components/AnalyticsPage.tsx) — dark variants
- Edit: [frontend/nginx.conf](../frontend/nginx.conf) — SSE-friendly proxy settings
- Edit: [CLAUDE.md](../CLAUDE.md) — document SSE endpoint, new deps, dark mode + shortcuts

## Reused

- [_persist_translation](../app/services/translator.py#L123), [_mark_failed](../app/services/translator.py#L267), [translate_book_batched](../app/services/translator.py#L300): just emit events, no logic change.
- [api.activateVersion](../frontend/src/api.ts) for "Use this version" inside the diff modal.
- [api.translateChunk](../frontend/src/api.ts) wrapped by `toast.promise` — no API change.
- Existing 3 s polling in [BookDetail.tsx:113-122](../frontend/src/components/BookDetail.tsx#L113-L122) — kept as SSE fallback rather than removed.
- Existing inline progress strip styling — moved into `BatchProgressBar`.

---

## Verification

1. **Toast smoke test**: upload a book → success toast bottom-right. Delete a book → success toast. Trigger a translate on a chunk with no model selected (force the 400) → error toast.
2. **SSE realtime**: open two browser tabs on the same book. Translate one chunk in tab A. Tab B updates within ~200 ms with no manual refresh. Confirm `Network → EventStream` in DevTools shows `chunk_updated` events. Kill the backend mid-stream; confirm frontend reconnects and the 3 s poll resumes as fallback. Restart backend; confirm reconnect.
3. **Batch progress bar**: trigger `Translate N pending` on a multi-chunk book. Sticky bar appears, `Stage 1 · n/N` updates per event, switches to `Stage 2` after phase boundary, disappears within 30 s of the last event.
4. **Filter**: select "Failed" chip with a mix of statuses; only failed chunks render. Type a word in search; filter narrows. Clear filter; full list returns.
5. **Version diff**: on a two-stage chunk, click "Compare" on the Stage-1 version. Modal opens. Stage 2 wording surfaces in green (added), Stage 1 in red (removed). Hit Esc → closes. Click "Use this version" → chunk activates the older version (existing endpoint), toast confirms.
6. **Dark mode**: click toggle. Header, sidebar, chunk cards, glossary, upload form all swap to dark palette with no contrast regressions. Reload → mode persists. Clear localStorage → falls back to OS preference.
7. **Shortcuts**: focus a chunk via `j`/`k` (ring visible). `t` queues translation (toast). `a` approves. `e` enters edit textarea. `/` focuses search. `?` shows help. None fire while a textarea has focus.
8. **No regression**: existing single-pass + two-stage paths still work end-to-end. CLAUDE.md is updated. `docker compose up --build` brings the stack up cleanly with the new dep and the SSE-friendly nginx config.

## Out of scope (deferred)

- Server-Sent Events authentication — no auth in this project yet, so the stream follows the existing security posture.
- Persistent notification center / history — toasts are ephemeral; add a `localStorage`-backed `<NotificationsDrawer>` later if users ask for history.
- Inline glossary highlighting on chunk text — separate concern, add when glossary churn becomes painful.
- Onboarding tour, reading mode, EPUB export — listed in the broader UX brainstorm but each deserves its own PR.
- Replacing 3 s polling entirely — keeping it as SSE fallback is safer and ~20 lines; ripping it out is a separate cleanup PR once SSE reliability is proven in prod.
