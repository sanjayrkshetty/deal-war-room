"use client";

import { useState } from "react";
import { api, ClauseRow, ScrubReport } from "@/lib/api";

const SOURCE_TYPES = [
  { value: "synthetic", label: "Synthetic (self-authored)" },
  { value: "sam_paste", label: "SAM.gov (pasted)" },
  { value: "gem_paste", label: "GeM (pasted)" },
  { value: "other_public", label: "Other public tender" },
];

export default function IngestPage() {
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState("synthetic");
  const [agency, setAgency] = useState("");
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<ScrubReport | null>(null);
  const [excerpt, setExcerpt] = useState<string | null>(null);
  const [committed, setCommitted] = useState<{ document_id: number; clause_count: number } | null>(null);
  const [clauses, setClauses] = useState<ClauseRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canPreview = text.trim().length > 0;
  const canCommit = title.trim().length > 0 && text.trim().length >= 50;

  async function handlePreview() {
    setError(null);
    setBusy(true);
    try {
      const result = await api.scrubPreview(text);
      setPreview(result.report);
      setExcerpt(result.scrubbed_excerpt);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleCommit() {
    setError(null);
    setBusy(true);
    try {
      const result = await api.createDocument({
        title,
        source_type: sourceType,
        agency: agency || null,
        external_ref: null,
        text,
      });
      setCommitted(result);
      const clauseList = await api.listClauses(result.document_id);
      setClauses(clauseList.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 font-mono text-zinc-200">
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-3">
        <a href="/" className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-400">
          DWR<span className="text-zinc-500">//</span>ingest
        </a>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">scrub gate · phase 1</span>
      </header>

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-4 p-6 lg:grid-cols-2">
        <section className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2">
            <label className="col-span-2 flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-widest text-zinc-500">title</span>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Tender title"
                className="border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs outline-none focus:border-emerald-500"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-widest text-zinc-500">source type</span>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
                className="border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs outline-none focus:border-emerald-500"
              >
                {SOURCE_TYPES.map((s) => (
                  <option key={s.value} value={s.value} className="bg-zinc-900">
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-widest text-zinc-500">agency / buyer</span>
              <input
                value={agency}
                onChange={(e) => setAgency(e.target.value)}
                placeholder="optional"
                className="border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs outline-none focus:border-emerald-500"
              />
            </label>
          </div>

          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-zinc-500">
              raw tender text — never stored, scrubbed before persistence
            </span>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={18}
              placeholder="Paste public tender or synthetic document text…"
              className="border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs leading-relaxed outline-none focus:border-emerald-500"
            />
          </label>

          <div className="flex gap-2">
            <button
              onClick={handlePreview}
              disabled={!canPreview || busy}
              className="border border-zinc-700 px-4 py-2 text-[11px] uppercase tracking-widest text-zinc-300 hover:border-emerald-500 disabled:opacity-40"
            >
              preview scrub
            </button>
            <button
              onClick={handleCommit}
              disabled={!canCommit || busy}
              className="border border-emerald-600 bg-emerald-950/40 px-4 py-2 text-[11px] uppercase tracking-widest text-emerald-300 hover:bg-emerald-900/40 disabled:opacity-40"
            >
              commit to vault
            </button>
          </div>

          {error && (
            <p className="border border-red-800 bg-red-950/40 px-3 py-2 text-xs text-red-400">{error}</p>
          )}
        </section>

        <section className="flex flex-col gap-4">
          {!preview && !committed && (
            <div className="flex h-full items-center justify-center border border-dashed border-zinc-800 p-8 text-center text-xs text-zinc-600">
              scrub audit and clause map render here
            </div>
          )}

          {preview && (
            <div className="border border-zinc-800 bg-zinc-900/40">
              <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-2">
                <h2 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-300">scrub audit</h2>
                <span className="text-[10px] text-zinc-500">{preview.scrubber_version}</span>
              </header>
              <div className="flex flex-wrap gap-2 p-3">
                {Object.entries(preview.categories).map(([cat, count]) => (
                  <span key={cat} className="border border-amber-700/50 bg-amber-950/30 px-2 py-1 text-[10px] uppercase tracking-wider text-amber-400">
                    {cat.replace(/_/g, " ")} × {count}
                  </span>
                ))}
                {preview.redactions_count === 0 && (
                  <span className="border border-zinc-700 px-2 py-1 text-[10px] uppercase tracking-wider text-zinc-400">
                    no redactions detected
                  </span>
                )}
              </div>
              {excerpt && (
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap border-t border-zinc-800/60 p-3 text-[11px] leading-relaxed text-zinc-400">
                  {excerpt}
                </pre>
              )}
            </div>
          )}

          {committed && (
            <div className="border border-zinc-800 bg-zinc-900/40">
              <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-2">
                <h2 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-300">clause map</h2>
                <span className="text-[10px] text-zinc-500">
                  doc #{committed.document_id} · {committed.clause_count} clauses
                </span>
              </header>
              <ul className="max-h-96 divide-y divide-zinc-800/60 overflow-auto">
                {clauses.map((clause) => (
                  <li key={clause.id} className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="border border-emerald-700/60 px-1.5 py-0.5 text-[10px] text-emerald-400">
                        §{clause.clause_ref}
                      </span>
                      {clause.heading && (
                        <span className="truncate text-xs text-zinc-300">{clause.heading}</span>
                      )}
                    </div>
                    <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-zinc-500">{clause.body}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
