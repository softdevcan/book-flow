const BASE = "/api";
async function request(path, init) {
    const res = await fetch(BASE + path, {
        headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
        ...init,
    });
    if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(`${res.status} ${res.statusText}: ${detail}`);
    }
    if (res.status === 204)
        return undefined;
    return (await res.json());
}
export const api = {
    listBooks: () => request("/books"),
    getBook: (id) => request(`/books/${id}`),
    deleteBook: (id) => request(`/books/${id}`, { method: "DELETE" }),
    uploadBook: async (form) => {
        const res = await fetch(BASE + "/books/upload", {
            method: "POST",
            body: form,
        });
        if (!res.ok) {
            const detail = await res.text().catch(() => "");
            throw new Error(`${res.status} ${res.statusText}: ${detail}`);
        }
        return (await res.json());
    },
    listChunks: (bookId) => request(`/books/${bookId}/chunks`),
    getChunk: (id) => request(`/chunks/${id}`),
    updateChunk: (id, payload) => request(`/chunks/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
    }),
    translateChunk: (id, overrides) => request(`/chunks/${id}/translate`, {
        method: "POST",
        body: JSON.stringify(overrides),
    }),
    translateBook: (id, overrides) => request(`/books/${id}/translate`, {
        method: "POST",
        body: JSON.stringify(overrides),
    }),
    listGlossary: (bookId) => request(`/books/${bookId}/glossary`),
    addGlossaryTerm: (bookId, source_term, target_term) => request(`/books/${bookId}/glossary`, {
        method: "POST",
        body: JSON.stringify({ source_term, target_term }),
    }),
    deleteGlossaryTerm: (id) => request(`/glossary/${id}`, { method: "DELETE" }),
    listModels: (provider) => request(`/models${provider ? `?provider=${encodeURIComponent(provider)}` : ""}`),
};
