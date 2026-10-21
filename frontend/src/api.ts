import type { AskResponse, Snapshot, SearchHit, UIConfig, Locale } from './types';
export class ApiError extends Error {
 status: number;
 constructor(status: number) { super(`HTTP ${status}`); this.status = status; }
}
async function request<T>(url: string, signal: AbortSignal, body?: object): Promise<T> {
 const response = await fetch(url, { signal, cache: 'no-store', method: body ? 'POST' : 'GET', headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined });
 if (!response.ok) throw new ApiError(response.status);
 return response.json() as Promise<T>;
}
export const getConfig = (signal: AbortSignal) => request<UIConfig>('/assistant/config', signal);
const payload = ({ question, settings }: Snapshot) => ({ question, source_language: settings.sourceLanguage === 'auto' ? null : settings.sourceLanguage, mode: settings.method, top_k: settings.topK });
export const ask = (snapshot: Snapshot, signal: AbortSignal) => request<AskResponse>('/assistant/ask', signal, { ...payload(snapshot), generator: snapshot.settings.generator, as_of: snapshot.settings.asOf || null, institution_type: snapshot.settings.institutionType || "credit_institution" });
export const search = (snapshot: Snapshot, sourceLanguage: Locale, signal: AbortSignal) => request<{ hits: SearchHit[] }>('/assistant/search', signal, { ...payload(snapshot), source_language: snapshot.settings.sourceLanguage === "auto" ? null : sourceLanguage });
export function officialLink(url: string, page?: number): string | null {
 try { const parsed = new URL(url); if (parsed.protocol !== 'https:' || !['bkam.ma', 'www.bkam.ma'].includes(parsed.hostname)) return null; parsed.hash = page ? `page=${page}` : ''; return parsed.toString(); } catch { return null; }
}
export const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError';
