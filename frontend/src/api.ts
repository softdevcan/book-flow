import type { Book, Chunk, GlossaryTerm, ModelsResponse } from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
}

export const api = {
  listBooks: () => request<Book[]>("/books"),
  getBook: (id: number) => request<Book>(`/books/${id}`),
  deleteBook: (id: number) =>
    request<void>(`/books/${id}`, { method: "DELETE" }),

  uploadBook: async (form: FormData): Promise<Book> => {
    const res = await fetch(BASE + "/books/upload", {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}: ${detail}`);
    }
    return (await res.json()) as Book;
  },

  listChunks: (bookId: number) =>
    request<Chunk[]>(`/books/${bookId}/chunks`),
  getChunk: (id: number) => request<Chunk>(`/chunks/${id}`),
  updateChunk: (id: number, payload: Partial<Chunk>) =>
    request<Chunk>(`/chunks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  translateChunk: (id: number, overrides: { provider?: string; model?: string }) =>
    request<Chunk>(`/chunks/${id}/translate`, {
      method: "POST",
      body: JSON.stringify(overrides),
    }),
  translateBook: (
    id: number,
    overrides: { provider?: string; model?: string },
  ) =>
    request<Chunk[]>(`/books/${id}/translate`, {
      method: "POST",
      body: JSON.stringify(overrides),
    }),

  listGlossary: (bookId: number) =>
    request<GlossaryTerm[]>(`/books/${bookId}/glossary`),
  addGlossaryTerm: (bookId: number, source_term: string, target_term: string) =>
    request<GlossaryTerm>(`/books/${bookId}/glossary`, {
      method: "POST",
      body: JSON.stringify({ source_term, target_term }),
    }),
  deleteGlossaryTerm: (id: number) =>
    request<void>(`/glossary/${id}`, { method: "DELETE" }),

  listModels: (provider?: string) =>
    request<ModelsResponse>(
      `/models${provider ? `?provider=${encodeURIComponent(provider)}` : ""}`,
    ),
};
