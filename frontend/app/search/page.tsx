"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Hit = {
  clause_id: number;
  doc_id: number;
  clause_ref: string;
  heading: string | null;
  score: number;
  snippet: string;
};

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [docs, setDocs] = useState<{ id: number; title: string }[]>([]);
  const [docFilter, setDocFilter] = useState<number | null>(null);
  const [hits, setHits] = useState<Hit[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    api
      .listDocuments()
      .then((res) => setDocs(res.items))
      .catch(() => setDocs([]));
  }, []);

  async function handleSearch() {
    setError(null);
    setBusy(true);
    try {
      const res = await api.search({ query, doc_id: docFilter, top_k: 10 });
      setHits(res.results);
      setSearched(true);
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
          DWR<span className="text-zinc-500">//</span>retrieval
        </a>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">MiniLM · brute-force cosine · phase 2</span>
      </header>

      <main className="mx-auto flex max-w-5xl flex-col gap-4 p-6">
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && query.trim() && handleSearch()}
            placeholder="Ask the corpus a question…"
            className="flex-1 border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs outline-none focus:border-emerald-500"
          />
          <select
            value={docFilter ?? ""}
            onChange={(e) => setDocFilter(e.target.value ? Number(e.target.value) : null)}
            className="border border-zinc-800 bg-zinc-900/60 px-2 py-2 text-xs outline-none focus:border-emerald-500"
          >
            <option value="" className="bg-zinc-900">all documents</option>
            {docs.map((d) => (
              <option key={d.id} value={d.id} className="bg-zinc-900">
                #{d.id} {d.title.slice(0, 30)}
              </option>
            ))}
          </select>
          <button
            onClick={handleSearch}
            disabled={!query.trim() || busy}
            className="border border-emerald-600 bg-emerald-950/40 px-4 py-2 text-[11px] uppercase tracking-widest text-emerald-300 hover:bg-emerald-900/40 disabled:opacity-40"
          >
            search
          </button>
        </div>

        {error && (
          <p className="border border-red-800 bg-red-950/40 px-3 py-2 text-xs text-red-400">{error}</p>
        )}

        {!searched && !error && (
          <div className="border border-dashed border-zinc-800 p-8 text-center text-xs text-zinc-600">
            retrieval debug panel — scores are cosine similarity over stored clause vectors
          </div>
        )}

        {searched && (
          <ul className="divide-y divide-zinc-800/60 border border-zinc-800 bg-zinc-900/40">
            {hits.length === 0 && (
              <li className="px-4 py-6 text-center text-xs text-zinc-600">no clauses matched</li>
            )}
            {hits.map((hit) => (
              <li key={hit.clause_id} className="px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="border border-emerald-700/60 px-1.5 py-0.5 text-[10px] text-emerald-400">
                      §{hit.clause_ref}
                    </span>
                    <span className="truncate text-xs text-zinc-300">{hit.heading ?? "—"}</span>
                  </div>
                  <span className="text-[10px] text-zinc-500">doc #{hit.doc_id}</span>
                </div>
                <div className="mt-1.5 h-0.5 w-full bg-zinc-800">
                  <div className="h-full bg-emerald-500" style={{ width: `${Math.min(100, hit.score * 100)}%` }} />
                </div>
                <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-500">{hit.snippet}</p>
                <p className="mt-1 text-right text-[10px] text-zinc-600">cos {hit.score.toFixed(4)}</p>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
