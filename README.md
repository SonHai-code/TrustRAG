# TrustRAG (Phase 0 + 1)

Agentic RAG over Vietnamese public legal documents. This drop contains the
infrastructure (Phase 0) and the ingestion pipeline (Phase 1).

## Step-by-step setup (beginner friendly)

🔴 **Requirements:** Python 3.11+, Docker Desktop (running), Git.

1. **Create the environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **Configure**: `cp .env.example .env` (🔴 never commit `.env`).
3. **Start services**: `docker compose up -d`, then check:
   - Qdrant dashboard: http://localhost:6333/dashboard
   - `docker compose ps` shows qdrant, redis, postgres as running.
4. **Run the tests** (no Docker or internet needed): `pytest -q` → 3 passed.
5. **Try the pipeline on the sample law**
   ```bash
   python -m ingestion.cli ingest --input data/sample --dry-run   # parse + chunk only
   python -m ingestion.cli ingest --input data/sample             # + embed + index
   python -m ingestion.cli search "thời hạn lưu trữ tài liệu quan trọng"
   ```
   🔴 The first real run downloads the `BAAI/bge-m3` model (~2.3 GB). This is normal.
   Expected: the top hit is **Điều 3. Thời hạn lưu trữ**.
6. **Add real documents**: put PDF/DOCX files in `data/raw/` (or list URLs in
   `data/sources.csv` and run `python -m ingestion.cli download`), then
   `python -m ingestion.cli ingest --input data/raw`.
   🔴 Only use documents you are legally allowed to reuse (government-published texts).
7. **Check quality by hand**: open `data/processed/chunks.jsonl`. Each line should be one
   Article with correct `article`, `chapter`, `article_title`. Fix the regexes in
   `ingestion/chunker.py` if your PDFs use a different heading style.
8. **Git**: `git init && git add . && git commit -m "Phase 0+1: infra and ingestion"`.

## How it works

`parse.py` (PDF/DOCX/TXT → text) → `chunker.py` (split by Chương/Điều/Khoản, keep metadata)
→ `embed.py` (bge-m3, 1024-d) → `index.py` (Qdrant, deterministic IDs so re-runs don't duplicate).

## Phase 1 checklist

- [ ] 200–500 documents in `data/raw/`
- [ ] Spot-check 20 chunks for correct boundaries
- [ ] 10 manual search questions return the right Article in the top 5 (note the results for the Phase 2 baseline)

---

# Phase 2: RAG API with citations, streaming and baseline metrics

```
question -> embed -> Qdrant top-k -> score gate -> LLM (answer with [n] markers) -> citations
```

Endpoints: `GET /health`, `GET /health/ready`, `POST /search` (retrieval only), `POST /chat` (structured JSON),
`POST /chat/stream` (Server-Sent Events: `sources` -> `token`... -> `done`). Interactive docs: http://localhost:8000/docs

## Step-by-step

1. 🔴 **Re-ingest first.** Phase 1 had two bugs, now fixed: chunks of long Articles overwrote each other
   (83 chunks became 74 points) and Word **tables** were skipped (e.g. the minimum-wage table). Rebuild the index:
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt            # adds fastapi, uvicorn, httpx
   colima stop -f                             # optional
   colima start                               # optional
   docker compose up -d                       # (colima start  first, if you use Colima)
   python -m ingestion.cli ingest --input data/sample --recreate
   ```
   Check the count: `curl -s localhost:6333/collections/legal_docs | python3 -m json.tool` (points_count should equal the chunk count printed by the ingest).
2. **Configure the LLM** in `.env` (see `.env.example`). 🔴 Never commit `.env`.
   - Claude: `LLM_PROVIDER=anthropic`, `LLM_API_KEY=sk-ant-...`
   - OpenAI-compatible (also your own vLLM later): `LLM_PROVIDER=openai`, `LLM_BASE_URL=...`, `LLM_MODEL=...`
   - No key yet: `LLM_PROVIDER=mock` returns a canned answer so you can test the whole API.
3. **Run the tests** (no Qdrant, model or key needed): `pytest -q`
4. **Start the API**: `uvicorn api.main:app --reload --port 8000` (the first start loads the embedding model, give it a minute).
5. **Try it**
   ```bash
   curl -s localhost:8000/health/ready
   curl -s -X POST localhost:8000/search -H 'Content-Type: application/json' \
     -d '{"question":"Mức lương tối thiểu vùng I là bao nhiêu?"}' | python3 -m json.tool
   curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' \
     -d '{"question":"Mức lương tối thiểu vùng I là bao nhiêu?"}' | python3 -m json.tool
   curl -N -X POST localhost:8000/chat/stream -H 'Content-Type: application/json' \
     -d '{"question":"Thời hiệu xử phạt vi phạm hành chính là bao lâu?"}'
   ```
6. **Record the baseline** (🔴 do this now, before Phase 3 changes anything):
   ```bash
   python -m scripts.baseline --label baseline              # retrieval metrics, no LLM needed
   python -m scripts.baseline --label baseline --with-llm   # + end-to-end latency, citations
   ```
   Results are appended to `eval/baseline_results.md`. Copy the table into the main README as the "before" row.
7. **Grow the question set** in `eval/questions.jsonl` to 30-50 questions. 🔴 Verify each expected Article by hand: these seed questions were written from Article titles only. Include out-of-scope questions (`"should_refuse": true`).
8. **Tune `MIN_SCORE`**: the baseline prints the lowest top-1 score of answerable questions and the highest of out-of-scope ones. Pick a threshold between them.

## Design notes (talking points)

- **Refusal gate**: below `MIN_SCORE` the API answers "not found" _without calling the LLM_ (cheaper, and no hallucination).
- **Citations are verified**: only `[n]` markers that map to a retrieved source are returned; invented markers are dropped; answers with no valid marker are flagged `grounded=false`.
- **Prompt-injection hygiene**: retrieved text is declared as data in the system prompt (full guardrails in Phase 7).
- **No vendor SDK**: plain `httpx` so any OpenAI-compatible server (vLLM) plugs in later.
- **Known limits (fixed in later phases)**: dense retrieval only (Phase 3), single-shot, no agent loop (Phase 4), `confidence` is just the top-1 retrieval score.

---

# Web UI (React + Vite + TypeScript)

`ui/` is a small chat app for the API: streaming answers, clickable `[n]` citation chips that open the source passage,
grounded/refusal badges, latency, a retrieval-only "search" mode and an API status indicator.

1. Install Node 18+ (check with `node -v`).
2. Start the API in one Terminal tab (`uvicorn api.main:app --reload --port 8000`).
3. In a second tab:
   ```bash
   cd ui
   npm install
   npm run dev
   ```
4. Open http://localhost:5173. 🔴 The browser talks to `/api/*`; Vite forwards it to port 8000 (see `ui/vite.config.ts`), so no CORS setup is needed in development.
5. Production build: `npm run build` (output in `ui/dist`). Serving it behind Nginx with a `/api` reverse proxy is part of Phase 8.
