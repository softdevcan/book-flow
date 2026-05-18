export type ChunkStatus = "raw" | "in_review" | "approved";

export interface Book {
  id: number;
  title: string;
  author: string | null;
  style_guide: string | null;
  total_chunks: number;
  created_at: string;
}

export interface Chunk {
  id: number;
  book_id: number;
  sequence_number: number;
  source_text: string;
  translated_text: string | null;
  status: ChunkStatus;
  editor_notes: string[] | null;
  scene_context: string | null;
}

export interface GlossaryTerm {
  id: number;
  book_id: number;
  source_term: string;
  target_term: string;
}

export interface ModelsResponse {
  provider: string;
  active_default: string | null;
  models: string[];
}
