"use client";

import { useEffect, useState } from "react";

type HealthState =
  | { status: "checking" }
  | { status: "up"; db_ok: boolean; groq_key_present: boolean; embedder_loaded: boolean }
  | { status: "down" };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

function Lamp({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2 border border-zinc-800 bg-zinc-900/60 px-3 py-1.5">
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-400" : "bg-red-500"}`} />
      <span className="text-[11px] uppercase tracking-widest text-zinc-400">{label}</span>
    </div>
  );
}

function Panel({ title, rows, href }: { title: string; rows: string[]; href?: string }) {
  const body = (
    <>
      <header className="border-b border-zinc-800 px-4 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-300">{title}</h2>
      </header>
      <ul className="divide-y divide-zinc-800/60">
        {rows.map((row) => (
          <li key={row} className="px-4 py-3 text-xs text-zinc-600">
            {row}
          </li>
        ))}
      </ul>
    </>
  );
  if (href) {
    return (
      <a href={href} className="block border border-zinc-800 bg-zinc-900/40 transition-colors hover:border-emerald-600">
        {body}
      </a>
    );
  }
  return <section className="border border-zinc-800 bg-zinc-900/40">{body}</section>;
}

export default function Home() {
  const [health, setHealth] = useState<HealthState>({ status: "checking" });

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/health`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((body) => {
        if (!cancelled) setHealth({ status: "up", ...body });
      })
      .catch(() => {
        if (!cancelled) setHealth({ status: "down" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const up = health.status === "up";

  return (
    <div className="min-h-screen bg-zinc-950 font-mono text-zinc-200">
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-3">
        <div className="flex items-baseline gap-3">
          <h1 className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-400">
            DWR<span className="text-zinc-500">//</span>Deal War Room
          </h1>
          <span className="text-[10px] uppercase tracking-widest text-zinc-600">phase 0 · skeleton</span>
        </div>
        <span className={`text-[10px] uppercase tracking-widest ${up ? "text-emerald-400" : "text-red-400"}`}>
          {health.status === "checking" ? "linking…" : up ? "api online" : "api offline"}
        </span>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-4 p-6">
        <div className="flex flex-wrap gap-2">
          <Lamp label="db" ok={up && health.db_ok} />
          <Lamp label="groq key" ok={up && health.groq_key_present} />
          <Lamp label="embedder" ok={up && health.embedder_loaded} />
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Panel title="Ingest" href="/ingest" rows={["paste gate · scrubber audit", "clause segmentation", "live · phase 1"]} />
          <Panel title="Retrieval" href="/search" rows={["MiniLM semantic search", "score + snippet debug", "live · phase 2"]} />
          <Panel title="Clauses" rows={["navigator rail", "citation drawer", "awaiting phase 4"]} />
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Panel title="Brief" href="/brief" rows={["bid-fit verdict strip", "traps · matrix · drivers", "live · phase 4"]} />
          <Panel title="Pipeline" rows={["triage → risk → synthesis", "citation enforcement", "live · phase 3"]} />
          <Panel title="Deploy" rows={["public showcase", "capped live analysis", "awaiting phase 5"]} />
        </div>

        <p className="border border-dashed border-zinc-800 px-4 py-3 text-[11px] text-zinc-600">
          Every claim will cite its clause. Uncited claims get suppressed. No drafting.
        </p>
      </main>
    </div>
  );
}
