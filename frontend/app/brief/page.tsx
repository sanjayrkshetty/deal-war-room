"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, Brief, ClauseFull, ClauseRow } from "@/lib/api";

type DocMeta = { id: number; title: string; clause_count: number };
type AnalysisState = { id: number; status: string; stage: string | null };

const SECTION_ORDER = [
  "scope_traps",
  "service_line_matrix",
  "effort_drivers",
  "eligibility_gates",
  "key_dates",
  "question_bank",
  "win_themes",
] as const;

const SECTION_TITLES: Record<string, string> = {
  scope_traps: "Scope Traps",
  service_line_matrix: "Service-Line Matrix",
  effort_drivers: "Effort Drivers",
  eligibility_gates: "Eligibility Gates",
  key_dates: "Key Dates",
  question_bank: "Client Question Bank",
  win_themes: "Win Themes",
};

const REC_STYLES: Record<string, string> = {
  GO: "border-emerald-500 bg-emerald-950/60 text-emerald-300",
  CONDITIONAL: "border-amber-500 bg-amber-950/60 text-amber-300",
  NO_GO: "border-red-500 bg-red-950/60 text-red-300",
};

const SEVERITY_STYLES: Record<string, string> = {
  HIGH: "border-red-600 text-red-400",
  MED: "border-amber-600 text-amber-400",
  LOW: "border-zinc-600 text-zinc-400",
};

function Badge({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center border px-2 py-0.5 text-[10px] uppercase tracking-widest ${className}`}>
      {children}
    </span>
  );
}

function CiteChip({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="border border-emerald-700/70 bg-emerald-950/30 px-1.5 py-0.5 text-[10px] text-emerald-300 hover:bg-emerald-900/50"
    >
      §{label}
    </button>
  );
}

function Drawer({
  clause,
  spans,
  onClose,
}: {
  clause: ClauseFull | null;
  spans: { start: number | null; end: number | null }[];
  onClose: () => void;
}) {
  if (!clause) return null;
  const normalized = clause.body.replace(/\s+/g, " ").trim();
  const marks = spans
    .filter((s) => s.start != null && s.end != null)
    .sort((a, b) => (a.start ?? 0) - (b.start ?? 0));
  const segments: { text: string; mark: boolean }[] = [];
  let cursor = 0;
  for (const m of marks) {
    const s = Math.max(0, Math.min(m.start!, normalized.length));
    const e = Math.max(s, Math.min(m.end!, normalized.length));
    if (s > cursor) segments.push({ text: normalized.slice(cursor, s), mark: false });
    segments.push({ text: normalized.slice(s, e) || normalized.slice(s), mark: true });
    cursor = e;
  }
  if (cursor < normalized.length) segments.push({ text: normalized.slice(cursor), mark: false });

  return (
    <div className="fixed inset-y-0 right-0 z-40 flex w-[520px] flex-col border-l border-zinc-700 bg-zinc-950 shadow-2xl">
      <header className="flex items-center justify-between border-b border-zinc-800 px-5 py-3">
        <div className="flex items-center gap-2">
          <Badge className="border-emerald-600 text-emerald-300">§{clause.clause_ref}</Badge>
          <span className="truncate text-xs text-zinc-300">{clause.heading ?? clause.document_title}</span>
        </div>
        <button onClick={onClose} className="text-xs uppercase tracking-widest text-zinc-500 hover:text-zinc-300">
          close
        </button>
      </header>
      <div className="flex-1 overflow-auto p-5">
        <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-zinc-300">
          {segments.map((seg, i) =>
            seg.mark ? (
              <mark key={i} className="bg-emerald-500/25 text-emerald-200">
                {seg.text}
              </mark>
            ) : (
              <span key={i}>{seg.text}</span>
            ),
          )}
        </p>
        {spans.length === 0 && (
          <p className="mt-3 border border-dashed border-zinc-800 p-2 text-[11px] text-zinc-500">
            no stored span offsets for this citation — clause shown in full
          </p>
        )}
      </div>
      <footer className="border-t border-zinc-800 px-5 py-2 text-[10px] uppercase tracking-widest text-zinc-600">
        doc #{clause.doc_id} · clause id {clause.id}
      </footer>
    </div>
  );
}

export default function BriefPage() {
  const [docs, setDocs] = useState<DocMeta[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<number | null>(null);
  const [clauses, setClauses] = useState<ClauseRow[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisState | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<{ clauseId: number; path: string } | null>(null);
  const [drawerClause, setDrawerClause] = useState<ClauseFull | null>(null);

  useEffect(() => {
    api.listDocuments().then((res) => {
      setDocs(res.items);
      if (res.items.length > 0) setSelectedDoc((cur) => cur ?? res.items[0].id);
    }).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (selectedDoc == null) return;
    setClauses([]);
    setBrief(null);
    setAnalysis(null);
    api.getClauses(selectedDoc).then((r) => setClauses(r.items)).catch(() => {});
    api
      .listBriefs(selectedDoc)
      .then((res) => {
        if (res.items.length > 0) {
          setAnalysis({ id: res.items[0].analysis_id, status: "done", stage: null });
        }
      })
      .catch(() => {});
  }, [selectedDoc]);

  const loadBrief = useCallback((analysisId: number) => {
    api.getBrief(analysisId).then((res) => {
      if (res.brief) setBrief(res.brief);
    }).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!analysis || analysis.status === "done" || analysis.status === "failed") {
      if (analysis?.status === "done") loadBrief(analysis.id);
      return;
    }
    const timer = setInterval(async () => {
      try {
        const state = await api.getAnalysis(analysis.id);
        setAnalysis({ id: state.id, status: state.status, stage: state.stage });
        if (state.status === "done") {
          clearInterval(timer);
          loadBrief(analysis.id);
        }
        if (state.status === "failed") {
          clearInterval(timer);
          setError(state.error ?? "pipeline failed");
        }
      } catch {
        /* transient */
      }
    }, 2500);
    return () => clearInterval(timer);
  }, [analysis, loadBrief]);

  useEffect(() => {
    if (!drawer) {
      setDrawerClause(null);
      return;
    }
    api.getClause(drawer.clauseId).then(setDrawerClause).catch((e) => setError(String(e)));
  }, [drawer]);

  const spansForDrawer = useMemo(() => {
    if (!brief || !drawer) return [];
    return brief.citations
      .filter((c) => c.claim_path === drawer.path && c.clause_id === drawer.clauseId)
      .map((c) => ({ start: c.span_start, end: c.span_end }));
  }, [brief, drawer]);

  async function runAnalysis() {
    if (selectedDoc == null) return;
    setError(null);
    try {
      const res = await api.startAnalysis(selectedDoc);
      setAnalysis({ id: res.analysis_id, status: res.status, stage: null });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function renderSection(name: string, items: Record<string, unknown>[]) {
    return (
      <section key={name} className="border border-zinc-800 bg-zinc-900/40">
        <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-300">
            {SECTION_TITLES[name] ?? name}
          </h2>
          <span className="text-[10px] text-zinc-600">{items.length}</span>
        </header>
        <ul className="divide-y divide-zinc-800/60">
          {items.map((item, i) => {
            const path = `${name}[${i}]`;
            const ids: number[] = Array.isArray(item.clause_ids) ? (item.clause_ids as number[]) : [];
            const title =
              (item.title as string) ??
              (item.question as string) ??
              (item.theme as string) ??
              (item.requirement as string) ??
              (item.driver as string) ??
              (item.label as string) ??
              ((item.line as string) ?? "");
            const detail =
              (item.why_trap as string) ??
              (item.intent as string) ??
              (item.supporting_evidence as string) ??
              (item.basis as string) ??
              (item.evidence as string) ??
              "";
            const metaBits = [
              item.severity,
              item.fit,
              item.status,
              item.priority,
              item.value,
              item.impact,
            ].filter(Boolean);
            return (
              <li key={path} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  {item.severity ? (
                    <Badge className={SEVERITY_STYLES[item.severity as string] ?? ""}>
                      {item.severity as string}
                    </Badge>
                  ) : null}
                  <span className="text-xs font-semibold text-zinc-200">{title}</span>
                  {metaBits.filter((b) => b !== item.severity).map((b, bi) => (
                    <span key={bi} className="text-[10px] uppercase tracking-wider text-zinc-500">
                      {String(b)}
                    </span>
                  ))}
                </div>
                {detail && <p className="mt-1 text-[12px] leading-relaxed text-zinc-400">{detail}</p>}
                <div className="mt-1.5 flex gap-1.5">
                  {ids.map((cid) => {
                    const clauseRow = clauses.find((c) => c.id === cid);
                    return (
                      <CiteChip
                        key={`${path}-${cid}`}
                        label={clauseRow ? clauseRow.clause_ref : `id:${cid}`}
                        onClick={() => setDrawer({ clauseId: cid, path })}
                      />
                    );
                  })}
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    );
  }

  const sections = brief
    ? SECTION_ORDER.filter((s) => {
        const val = (brief.payload as Record<string, unknown>)[s];
        return Array.isArray(val) && val.length > 0;
      }).map((s) => ({ name: s, items: (brief.payload as Record<string, unknown>)[s] as Record<string, unknown>[] }))
    : [];

  const verdict = brief?.payload.verdict;
  const meta = brief?.payload.meta;

  return (
    <div className="min-h-screen bg-zinc-950 font-mono text-zinc-200">
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-3">
        <a href="/" className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-400">
          DWR<span className="text-zinc-500">//</span>brief
        </a>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">
          decision brief · phase 4
        </span>
      </header>

      <div className="mx-auto flex max-w-[1600px] gap-4 p-4">
        <aside className="hidden w-64 shrink-0 flex-col gap-3 lg:flex">
          <section className="border border-zinc-800 bg-zinc-900/40">
            <header className="border-b border-zinc-800 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-400">
              Documents
            </header>
            <ul className="max-h-56 overflow-auto divide-y divide-zinc-800/60">
              {docs.map((d) => (
                <li key={d.id}>
                  <button
                    onClick={() => setSelectedDoc(d.id)}
                    className={`block w-full px-3 py-2 text-left text-xs hover:bg-zinc-800/40 ${
                      selectedDoc === d.id ? "bg-zinc-800/60 text-emerald-300" : "text-zinc-400"
                    }`}
                  >
                    <span className="text-[10px] text-zinc-600">#{d.id}</span> {d.title.slice(0, 34)}
                  </button>
                </li>
              ))}
              {docs.length === 0 && (
                <li className="px-3 py-3 text-xs text-zinc-600">ingest a document first</li>
              )}
            </ul>
          </section>

          <section className="border border-zinc-800 bg-zinc-900/40">
            <header className="border-b border-zinc-800 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-400">
              Clauses
            </header>
            <ul className="max-h-80 overflow-auto divide-y divide-zinc-800/60">
              {clauses.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => setDrawer({ clauseId: c.id, path: "__navigator__" })}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[11px] text-zinc-500 hover:bg-zinc-800/40"
                  >
                    <span className="text-emerald-600">§{c.clause_ref}</span>
                    <span className="truncate">{c.heading ?? c.body.slice(0, 30)}</span>
                  </button>
                </li>
              ))}
              {clauses.length === 0 && (
                <li className="px-3 py-3 text-xs text-zinc-600">—</li>
              )}
            </ul>
          </section>
        </aside>

        <main className="min-w-0 flex-1 flex-col gap-4">
          {error && (
            <p className="border border-red-800 bg-red-950/40 px-3 py-2 text-xs text-red-400">{error}</p>
          )}

          {!selectedDoc && (
            <div className="border border-dashed border-zinc-800 p-10 text-center text-xs text-zinc-600">
              ingest and analyze a document to see its decision brief
            </div>
          )}

          {selectedDoc && !brief && !analysis && (
            <div className="flex flex-col items-start gap-3 border border-dashed border-zinc-800 p-8">
              <p className="text-xs text-zinc-500">no analysis yet for doc #{selectedDoc}</p>
              <button
                onClick={runAnalysis}
                className="border border-emerald-600 bg-emerald-950/40 px-4 py-2 text-[11px] uppercase tracking-widest text-emerald-300 hover:bg-emerald-900/40"
              >
                run analysis
              </button>
            </div>
          )}

          {analysis && !brief && analysis.status !== "done" && (
            <div className="border border-zinc-800 bg-zinc-900/40 p-6">
              <div className="flex items-center gap-3">
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-400" />
                <span className="text-xs uppercase tracking-widest text-amber-300">
                  {analysis.status === "failed" ? "failed" : analysis.stage ?? analysis.status}
                </span>
              </div>
              <p className="mt-2 text-[11px] text-zinc-600">
                triage → risk → synthesis → enforcement · polling…
              </p>
            </div>
          )}

          {verdict && brief && (
            <div className="flex flex-col gap-4">
              <section className="grid grid-cols-[auto_1fr_auto] items-center gap-6 border border-zinc-700 bg-gradient-to-r from-zinc-900 to-zinc-900/40 px-6 py-4">
                <div className="flex items-baseline gap-2">
                  <span className="text-5xl font-bold tabular-nums text-zinc-100">
                    {verdict.bid_fit_score}
                  </span>
                  <span className="text-xs text-zinc-600">/100</span>
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className={`px-3 py-1 text-xs ${REC_STYLES[verdict.recommendation] ?? ""}`}>
                      {verdict.recommendation}
                    </Badge>
                    <Badge className="border-zinc-700 text-zinc-400">
                      conf {verdict.confidence ?? "?"}
                    </Badge>
                    {(meta?.uncited_claims_count ?? 0) > 0 && (
                      <Badge className="border-amber-700 text-amber-400">
                        integrity: {meta?.uncited_claims_count} suppressed
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1.5 truncate text-[11px] text-zinc-500">{verdict.rationale}</p>
                </div>
                <div className="text-right text-[10px] leading-relaxed text-zinc-600">
                  pipeline {meta?.pipeline_version} · rubric v{meta?.rubric_version}
                  <br />
                  {(meta?.model_config.triage ?? "").split("/").pop()} →{" "}
                  {(meta?.model_config.synthesis ?? "").split("/").pop()}
                </div>
              </section>

              <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                {sections.map(({ name, items }) => renderSection(name, items))}
              </div>

              <p className="border-t border-zinc-800/60 pt-2 text-[10px] text-zinc-600">
                every claim above is enforced against stored clauses · uncited claims are suppressed,
                never shown
              </p>
            </div>
          )}
        </main>
      </div>

      {drawer && (
        <Drawer clause={drawerClause} spans={spansForDrawer} onClose={() => setDrawer(null)} />
      )}
    </div>
  );
}
