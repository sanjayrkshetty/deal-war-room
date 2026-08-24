# Deal War Room — Build Plan v1.1

> Supersedes scoper spec after adversarial review (critic verdict: FIX FIRST).
> Status: APPROVED by owner 2026-08-24. Phase 5 (SAM.gov API client) CUT.

## Locked decisions

1. **Input:** operator-pasted text only — self-authored synthetic fixtures + manually pasted public tenders (SAM.gov/GeM). Never real client documents. DLP gate mandatory on every ingest.
2. **Output:** one Deal Decision Brief per document — bid-fit signal, scope traps, service-line matrix (DFIR/VAPT/GRC/SOC/red-team), effort drivers, eligibility gates, key dates, question bank, win themes. **Every claim cited to a stored clause. Uncited claims are suppressed, never rendered.** No proposal drafting, ever.
3. **Stack:** Next.js 15 + Tailwind · FastAPI + Groq · local MiniLM embeddings · SQLite.
4. **Verdict math:** deterministic, versioned SISA rubric in code (Option A). LLM proposes tags/traps; code computes score + GO/CONDITIONAL/NO_GO.
5. **Deployment:** public showcase, free tiers, no auth. Capped live analysis (server-side daily Groq budget + rate limit). Ephemeral DB accepted — fixtures reseed on boot. Repo stays private until launch-audit, flips public for LinkedIn.
6. **Ecosystem:** app first. Plain modules. Framework extraction is a future milestone with its own spec.

## Phases

### Phase 0 — Reset & skeleton (~7h)
Tag `v1-final`. Delete: Streamlit app, fake agents, TF-rag, html/docx exporters.
Monorepo: `backend/` (FastAPI + `dwr/` package), `frontend/` (Next.js 15 + Tailwind dark-terminal tokens).
Backend venv **pinned to Python 3.11 or 3.12** (repo shows 3.14 pycache; torch wheels gamble otherwise).
SQLite connection factory applies `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000` **on every open** (per-connection pragmas). Default DB path `%LOCALAPPDATA%\dwr\dwr.db` (env `DWR_DB_PATH`) — outside OneDrive-synced tree.
`schema.sql` + `PRAGMA user_version` migrations. `/health` returns `{db_ok, groq_key_present, embedder_loaded}`.
Next.js shell + health ping. Port scrubber tests unchanged.
**Accept:** pytest green; uvicorn /health ok; shell renders; `git grep -i docx` empty.

### Phase 1 — Scrubber gate + clause ingestion (~16h)
Port scrubber with three verified bug fixes: Indian mobile formats (10-digit contiguous / 5-5 groups), lakh-crore commercial grouping (`₹5,00,000` currently half-redacts), redaction counter counts actual substitutions not categories.
Single strict profile for ALL input. Name lists → config file. Scrub report stores categories + counts + hashes — **never matched strings**.
Deterministic clause segmenter (`segmenter_version` column on documents): numbered headings (`§x.y`, `Section N`, `4.2`) → clause_ref/heading/body/ordinal; unnumbered regions → **non-overlapping** ~800-char chunks (`C-001…`) to avoid citation ambiguity; tables kept verbatim in clause body.
Dedupe key `(raw_sha256, ingest_pipeline_version)`; admin `POST /documents/{id}/reindex` cascades clauses→embeddings→analyses→briefs.
Paste UI: textarea, source-type selector, scrub-audit preview before commit, clause map after.
Fixtures rewritten to clause-ID JSON + engineered traps + **prompt-injection canary fixture** + 2 real SAM.gov notices manually pasted into eval set (public info, permitted).
Tests: zero raw bytes persisted (DB introspection); boundary-F1 vs hand-marked references incl. real-format docs; dedupe/reindex behavior; scrubber suite green.
**Accept:** paste → redaction report → clause map, on synthetic AND real-pasted tender text.

### Phase 2 — Embeddings & retrieval (~7h)
`sentence-transformers/all-MiniLM-L6-v2`, **revision hash pinned**, CPU wheels forced, loaded once in app lifespan. Float32 BLOBs keyed by clause_id + model/dim columns. Brute-force numpy cosine (revisit trigger: 10k clauses). Backfill command. `POST /search` + debug panel.
**Accept:** SLA-question hits SLA clause top-3 on all fixtures; <200ms @ 500 clauses warm.

### Phase 3 — Agent pipeline + citation enforcement (~18h)
`dwr/llm.py`: Groq wrapper — env-pinned model names (`DWR_MODEL_TRIAGE`, `DWR_MODEL_SYNTH`), timeout/backoff, token budget, `dropped_clauses_count` surfaced when truncation drops Stage-1-relevant clauses.
Stages:
0. Pre-flight (code): re-verify scrubbed state; load clause map.
1. TRIAGE (cheap model, json_schema): batch 8–12 clauses → relevant/topic/service-line tags.
2. RISK PASS (strong model): scope_traps + effort_drivers + eligibility_gates + key_dates, each with clause_ids + quoted_spans.
3. SYNTHESIS (strong model): brief draft — tags/traps/themes only. **LLM never emits the numeric score or recommendation.**
4. ENFORCEMENT (pure code): clause-ID existence; span validator = rapidfuzz `partial_ratio ≥85` against **the cited clause body only**, min span 8 tokens/40 chars, persists char offsets for UI highlighting; exactly ONE repair round-trip; still-failing claims **removed from payload**, counted in `meta.uncited_claims_count`; integrity banner in UI.
Malformed-JSON policy Stages 1–3: pydantic-validate → one retry with error appended → clean stage failure.
Untrusted-input hardening: tender text wrapped in hard delimiters, system prompts declare marker content is data-not-instructions; out-of-band check that recommendation matches computed score; injection-canary in eval set must not move the verdict.
Background execution: async endpoints + `asyncio.to_thread`, single-flight lock per document, startup recovery marks stale `running`→`failed`, stage transitions written to DB for polling.
Rubric: versioned config (`rubric.yaml`) encoding SISA weights; echoed into `model_config_json`.
CLI runner `python -m dwr.analyze <doc_id>`.
Golden-file tests with stubbed transport (zero network by default) + one `@live` smoke test that fails with an actionable env-var message on model decommission.
**Accept:** CLI prints validated brief for Acme fixture; injection canary passes; <90s largest fixture.

### Phase 4 — Decision Brief UI (~13h)
Verdict strip always visible (score, GO/CONDITIONAL/NO_GO, confidence). Clause-navigator rail. Grid: scope traps (severity) → service-line matrix → effort drivers → eligibility gates + key dates → question bank → win themes. Claim chip → drawer with cited clause + highlighted char offsets.
Win-theme lint guard: ≤25 words, clause_ids mandatory (anti-drafting-creep).
Component kit ≤6 primitives. Manual QA checklist gates everything (no Playwright without explicit approval); vitest covers data transforms only.
**Accept:** manual checklist passes on all fixtures; every rendered claim resolves to clickable cited clause; density sign-off by owner eyeball at 1440×900.

### Phase 5 — Deploy & hardening (~6h, replaces old SAM phase)
Vercel free (frontend) + Render/Fly free (FastAPI). Ephemeral SQLite: boot-seed from synthetic fixtures. Server-side daily Groq token budget + per-IP rate limit; graceful degradation page when cap hit. Secrets server-env only. CORS/rewires via next.config. Two-machine verification + demo script.
Pre-public-flip audit: grep for sensitive strings, verify scrubber on live paths, quota caps confirmed.
**Accept:** public URL survives a cold visit; demo script clean; cap degradation works.

## Estimate rollup
7 + 16 + 7 + 18 + 13 + 6 = **67h point · 60–80h range · ~7–8 weeks part-time (10–12h/wk)**.
Critic-adjusted from naive 57h/3–5wk claim. Named cuts already applied (SAM client dead).

## Brief payload schema (v1.1)
```
verdict:            {bid_fit_score, recommendation GO|CONDITIONAL|NO_GO, rationale, citations[]}
eligibility_gates:  [{requirement, status MET|UNMET|UNKNOWN, clause_ids[]}]
key_dates:          [{label, value, clause_ids[]}]        # submission deadline, pre-bid, Q&A cutoff
scope_traps:        [{title, severity HIGH|MED|LOW, why_trap, clause_ids[], quoted_spans[]}]
service_line_matrix:[{line DFIR|VAPT|GRC|SOC|RED_TEAM, fit STRONG|PARTIAL|WEAK|NOT_REQUESTED,
                      evidence, clause_ids[]}]
effort_drivers:     [{driver, impact, basis, clause_ids[]}]
question_bank:      [{question, intent, priority, clause_ids[]}]
win_themes:         [{theme≤25w, supporting_evidence, clause_ids[]}]
meta:               {uncited_claims_count, dropped_clauses_count, pipeline_version, generated_at}
```

## Scope-creep register (trimmed)
Proposal-drafting requests → exporters deleted, requests logged post-v2 · Real client docs → mechanical gate, no bypass flag · GeM scraping → written decision record, paste UX instead · Premature framework abstraction → plain modules, review-enforced · Citation perfectionism → bounded repair then suppress-and-ship · UI polish black hole → primitive cap + density criteria · Portfolio/dashboard sprawl → out of scope, single-document product.

## Open item
Rubric calibration source (owner choice pending):
(a) structured questionnaire answered by owner (~15 min, zero exposure) — RECOMMENDED;
(b) supervised numeric-only mining of 2–3 representative proposals under owner supervision (effort benchmarks extracted, names/pricing/clients redacted on sight, nothing raw persisted);
(c) both.
OneDrive proposals path noted but NOT touched until explicit go.
