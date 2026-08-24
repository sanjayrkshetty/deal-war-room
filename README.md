# Deal War Room (`deal-war-room`) — v2

Citation-enforced tender deal intelligence. Paste a public/synthetic tender,
get a Deal Decision Brief where every claim traces to a stored clause.
No proposal drafting. No real client documents. Ever.

Full build contract: [`PLAN.md`](./PLAN.md)

## Status

Phase 0 — skeleton. Backend FastAPI + SQLite schema live; Next.js shell next.

## Quickstart

```bash
# backend (Python 3.11 pinned via uv)
cd backend
uv sync
uv run pytest
uv run uvicorn dwr.main:app --reload --port 8000

# frontend (Node 18.18+)
cd frontend
npm install
npm run dev
```

## Non-negotiables

1. Inputs: operator-pasted synthetic/public-tender text only, DLP gate on every ingest.
2. Every brief claim cites a clause; uncited claims are suppressed, never rendered.
3. Verdict math lives in versioned code (`rubric.yaml`), never in LLM output.
