export type ChunkStatus = "raw" | "in_review" | "approved";

export interface Book {
  id: number;
  title: string;
  author: string | null;
  style_guide: string | null;
  source_language: string;
  target_language: string;
  total_chunks: number;
  created_at: string;
}

export interface LangOption {
  code: string;
  name: string;
}

export interface LangDetection {
  code: string;
  confidence: number;
  method: "lib" | "llm";
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
  active_version_id: number | null;
}

export interface TranslationVersion {
  id: number;
  chunk_id: number;
  translated_text: string;
  editor_notes: string[] | null;
  pipeline: string | null;
  stage1_model: string | null;
  stage2_model: string | null;
  created_at: string;
}

export interface GlossaryTerm {
  id: number;
  book_id: number;
  source_term: string;
  target_term: string;
}

export interface ModelsResponse {
  provider: string;
  pipeline: "single" | "two_stage";
  /** What .env asks for — may not be installed. */
  configured_default: string | null;
  /** The default that will actually run (installed), or null if none installed. */
  active_default: string | null;
  stage_defaults: { stage1: string; stage2: string };
  models: string[];
}
