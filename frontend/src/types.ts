export type Locale = 'fr' | 'ar';
export type Method = 'bm25' | 'semantic' | 'hybrid';
export type Generator = 'extractive' | 'ollama';
export type SourceLanguage = 'auto' | Locale;
export interface Source { edition_label?: string; publication_date?: string; signature_date?: string; page_range?: number[]; review_status?: string; version_relations?: string; id: string; language: Locale; title: string; source_url: string; version_date: string; pdf_sha256: string; article_count: number | null; page_count?: number | null }
export interface UIConfig { profile?: { domain_loaded: boolean; generation_enabled?: boolean };
 corpus_label?: string; schema_version: number; ready: boolean; corpus_version: string; article_count: number;
 article_count_by_language: Record<Locale, number>; backend: string;
 encoder: { configured: string; loaded: boolean; name: string | null; dimension: number | null; preprocessing: string | null };
 available_modes: Method[]; supported_languages: Locale[]; policy_status: string;
 generators: { default: string; choices: Generator[]; ollama: { configured: boolean; model: string; availability: string; probe_performed: boolean } };
 request_limits: { question_min_length: number; question_max_length: number; top_k_min: number; top_k_max: number; top_k_default: number };
 sources: Source[]; score_is_probability: false;
}
export interface Citation { document_title?: string; edition_label?: string; chunk_id: string; source_id: string; document_id: string; article_id: string; language: Locale; source_url: string; page_start: number; page_end: number; version_date: string; sha256: string; quote: string }
export interface AskResponse { assessment?: Assessment; corpus_label?: string; status: 'abstained' | 'evidence_found'; answer: string; citations: Citation[]; query_language: Locale; source_language: Locale; retriever: Method; generator: Generator; corpus_version: string; semantic_faithfulness: string; reason: string | null; latency_ms: number; policy_status?: string }
export interface SearchHit { chunk_id: string; article_id: string; language: Locale; text: string; score: number; lexical_score: number | null; semantic_score: number | null; ranks: Record<string, number> }
export interface RequestSettings { asOf?: string; institutionType?: "credit_institution" | "bank" | "payment_institution" | "unknown"; sourceLanguage: SourceLanguage; method: Method; generator: Generator; topK: number }
export interface Snapshot { question: string; settings: RequestSettings }
export type RequestState = 'idle' | 'loading' | 'done' | 'error' | 'cancelled';
export interface HistoryEntry { id: string; snapshot: Snapshot; result: AskResponse | null; state: RequestState; error: number | null; at: number }

export interface AssistantClaim { id: string; text: string; citation_indices: number[] }
export interface Assessment { status: "complete" | "partial" | "absent" | "temporal" | "ambiguous"; message: string; claims?: AssistantClaim[]; findings: { key: string; label: string; state: "supported" | "missing"; citation_indices: number[] }[]; missing_points: string[]; clarification: string | null; scope_note: string; available_source_hint?: string }
