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

export type Brief = {
  id: number;
  analysis_id: number;
  doc_id: number;
  bid_fit_score: number | null;
  recommendation: string;
  confidence: string | null;
  uncited_claims_count: number;
  dropped_clauses_count: number;
  created_at: string;
  payload: {
    verdict: {
      bid_fit_score: number;
      recommendation: "GO" | "CONDITIONAL" | "NO_GO";
      rationale: string;
      confidence: string;
      no_go_signal_ids?: string[];
      conditional_signal_ids?: string[];
    };
    meta: {
      uncited_claims_count: number;
      dropped_clauses_count: number;
      pipeline_version: string;
      rubric_version: string;
      model_config: Record<string, string>;
    };
  } & Record<string, unknown>;
  citations: {
    claim_path: string;
    clause_id: number;
    quoted_span: string;
    span_start: number | null;
    span_end: number | null;
  }[];
};

export type ClauseFull = {
  id: number;
  doc_id: number;
  clause_ref: string;
  heading: string | null;
  body: string;
  ordinal: number;
  document_title: string;
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
  listBriefs: (docId?: number) =>
    request<{ items: { id: number; analysis_id: number; doc_id: number; bid_fit_score: number | null; recommendation: string; created_at: string }[] }>(
      `/api/v1/briefs${docId != null ? `?doc_id=${docId}` : ""}`,
    ),
  getBrief: (analysisId: number) =>
    request<{ status: string; error: string | null; brief: Brief | null }>(
      `/api/v1/analyses/${analysisId}/brief`,
    ),
  startAnalysis: (docId: number) =>
    request<{ analysis_id: number; status: string }>("/api/v1/analyses", {
      method: "POST",
      body: JSON.stringify({ document_id: docId }),
    }),
  getAnalysis: (analysisId: number) =>
    request<{ id: number; status: string; stage: string | null; error: string | null }>(
      `/api/v1/analyses/${analysisId}`,
    ),
  getClauses: (docId: number) =>
    request<{ items: ClauseRow[] }>(`/api/v1/documents/${docId}/clauses`),
  getClause: (clauseId: number) =>
    request<ClauseFull>(`/api/v1/clauses/${clauseId}`),
};
