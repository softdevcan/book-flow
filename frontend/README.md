# BookFlow Frontend

Vite + React + TypeScript + Tailwind. Talks to the FastAPI backend via the proxy in `vite.config.ts`.

## Develop

```bash
npm install
npm run dev
```

Opens on `http://localhost:5273`. Requires the backend to be running on `http://localhost:8200`.

To point at a different backend (e.g. when running outside Docker against a remote API):

```bash
VITE_BACKEND_URL=http://192.168.1.42:8200 npm run dev
```

## Build

```bash
npm run build
npm run preview
```

## Docker

A multi-stage `Dockerfile` builds the SPA and serves it with nginx on port `5273`. nginx also proxies `/api` and `/health` to the backend container (`backend:8200`) so the same relative API paths work in production.

```bash
docker build -t bookflow-frontend .
docker run -p 5273:5273 bookflow-frontend
```

In normal use, run via the root `docker-compose.yml`, which wires backend + frontend together.

## Layout

```
src/
├── main.tsx                     React entrypoint
├── App.tsx                      View switcher (library ↔ book detail)
├── api.ts                       Typed fetch client
├── types.ts                     TS mirrors of backend schemas
├── index.css                    Tailwind base
└── components/
    ├── BookList.tsx             Library view + upload form
    ├── UploadForm.tsx           Multipart upload, chunk-size slider
    ├── BookDetail.tsx           Chunks list, polling, batch translate
    ├── ChunkCard.tsx            Source/translation side-by-side, edit, approve
    ├── ModelPicker.tsx          Dropdown populated from /api/models
    └── GlossaryPanel.tsx        Add / list / remove glossary terms
```

## Patterns

- Plain `useState` + `useEffect`. No global state library.
- `BookDetail` polls `/api/books/{id}/chunks` every 3 s while any chunk is `raw` with no translation, and stops automatically.
- `ModelPicker` calls `/api/models` to populate the dropdown. The default (from `.env`) is shown as the first option; selecting a different value sends `model` in the translate request body.
- All API paths are relative — the Vite proxy forwards `/api` and `/health` to the backend.

## Adding a view

1. Build a new component under `src/components/`.
2. Either route through `App.tsx`'s view switcher or wire it inside `BookDetail`.
3. If you need a new endpoint, add it to `src/api.ts` and add the matching backend route.
