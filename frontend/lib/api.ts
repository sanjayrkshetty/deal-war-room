export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type ScrubReport = {
  scrubber_version: string;
  redactions_count: number;
  categories: Record<string, number>;
  input_sha256: string;
  output_sha256: string;
};

export type ClauseRow = {
  id: number;
  clause_ref: string;
  heading: string | null;
  body: string;
  ordinal: number;
  segmentation_mode: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ db_ok: boolean; groq_key_present: boolean; embedder_loaded: boolean }>("/health"),
  scrubPreview: (text: string) =>
    request<{ redactions_count: number; report: ScrubReport; scrubbed_excerpt: string }>(
      "/api/v1/scrub-preview",
      { method: "POST", body: JSON.stringify({ text }) },
    ),
  createDocument: (payload: {
    title: string;
    source_type: string;
    agency?: string | null;
    external_ref?: string | null;
    text: string;
  }) =>
    request<{ document_id: number; clause_count: number; segmentation_modes: string[]; scrub_report: ScrubReport }>(
      "/api/v1/documents",
      { method: "POST", body: JSON.stringify(payload) },
    ),
  listClauses: (docId: number) =>
    request<{ items: ClauseRow[] }>(`/api/v1/documents/${docId}/clauses`),
  listDocuments: () =>
    request<{ items: { id: number; title: string; clause_count: number }[]; total: number }>(
      "/api/v1/documents",
    ),
  search: (payload: { query: string; doc_id?: number | null; top_k?: number }) =>
    request<{
      query: string;
      results: {
        clause_id: number;
        doc_id: number;
        clause_ref: string;
        heading: string | null;
        score: number;
        snippet: string;
      }[];
    }>("/api/v1/search", { method: "POST", body: JSON.stringify(payload) }),
};
