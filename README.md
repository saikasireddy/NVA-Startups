# NVA Mentoring Startups Guide Chatbot

Local-first Retrieval-Augmented Generation (RAG) assistant for the New Venture Accelerator (NVA).

## What This Project Does

- Uses `Mentoring Startups GuideF.docx` as the knowledge base.
- Creates a FAISS vector index from the guide (`backend/ingest.py`).
- Runs a FastAPI backend with:
  - local Ollama LLM (`llama3` by default),
  - SQLite conversation memory (`chat_history.db`),
  - streaming responses,
  - rate limiting,
  - history/auditing endpoints.
- Runs a Next.js frontend with a polished chat UI and per-session thread IDs.

## Project Structure

- `backend/` FastAPI API, ingestion script, vector/index loading, memory, tracing.
- `frontend/` Next.js App Router chat client + API proxy route.
- `Mentoring Startups GuideF.docx` source document used for RAG.

## Tech Stack

- Backend: FastAPI, LangChain LCEL, FAISS, SQLAlchemy, SlowAPI, Ollama, Phoenix.
- Frontend: Next.js App Router, React, Tailwind, Vercel AI SDK (`useChat`).

---

## Step-by-Step Local Setup (Windows CMD Friendly)

### 1) Prerequisites

- Python 3.12 recommended.
- Node.js available (`node -v`, `npm -v`).
- Ollama installed (`ollama --version`).

### 2) Backend virtual environment

```bat
cd "C:\Users\smk0101\OneDrive - Auburn University\Documents\NVA Project\backend"
py -3.12 -m venv .venv
.\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3) Build FAISS index (run once or after guide changes)

```bat
cd "C:\Users\smk0101\OneDrive - Auburn University\Documents\NVA Project\backend"
.\.venv\Scripts\activate.bat
python ingest.py
```

Expected output includes: `FAISS index saved to: ...\backend\faiss_index`

### 4) Start Ollama and pull model

Terminal A:

```bat
ollama serve
```

Terminal B (first time only):

```bat
ollama run llama3
```

### 5) (Optional) Start Phoenix observability

```bat
phoenix serve
```

Phoenix UI is usually at [http://127.0.0.1:6006](http://127.0.0.1:6006).

### 6) Start backend API

```bat
cd "C:\Users\smk0101\OneDrive - Auburn University\Documents\NVA Project\backend"
.\.venv\Scripts\activate.bat
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

If port 8000 is already used:

```bat
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### 7) Start frontend

```bat
cd "C:\Users\smk0101\OneDrive - Auburn University\Documents\NVA Project\frontend"
copy .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Quick End-to-End Test Checklist

1. Backend health:
   - [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
2. Ask two related chat questions in UI.
3. Confirm persistent memory:
   - [http://127.0.0.1:8000/api/history/sessions?page=1&page_size=20](http://127.0.0.1:8000/api/history/sessions?page=1&page_size=20)
   - `GET /api/history/{session_id}`
4. Confirm rate limiting by sending >10 prompts/minute from same client.

---

## Backend Environment Variables

- `DOCX_PATH` path to source docx.
- `FAISS_INDEX_DIR` FAISS directory (default `backend/faiss_index`).
- `FRONTEND_URL` allowed origin when CORS wildcard disabled.
- `CORS_ALLOW_ALL` default `true` for local ease.
- `OLLAMA_MODEL` default `llama3`.
- `OLLAMA_TEMPERATURE` default `0.2`.
- `OLLAMA_NUM_PREDICT` default `220`.
- `OLLAMA_NUM_CTX` default `2048`.
- `RETRIEVER_K` default `4`.
- `MAX_HISTORY_TURNS` default `3`.

To initialize backend env quickly:

```bat
cd "C:\Users\smk0101\OneDrive - Auburn University\Documents\NVA Project\backend"
copy .env.example .env
```

### Fast Mode (lower latency)

Use these before starting backend:

```bat
set OLLAMA_MODEL=llama3.2:3b
set RETRIEVER_K=3
set MAX_HISTORY_TURNS=2
set OLLAMA_NUM_PREDICT=160
set OLLAMA_NUM_CTX=1536
```

---

## API Contract

### `POST /api/chat`

- Streams plain text response tokens.
- Request body:

```json
{
  "session_id": "uuid-session-id",
  "messages": [
    { "role": "user", "content": "How should mentors handle founder conflict?" }
  ]
}
```

### `GET /api/history/{session_id}`

- Returns full persisted conversation for one session.

### `GET /api/history/sessions?page=1&page_size=20`

- Returns paginated list of sessions (latest first) with preview and counts.

---

## Common Issues and Fixes

### `pip` not recognized

Use:

```bat
py -m pip install -r requirements.txt
```

### `ollama` not recognized

- Reopen terminal after install, or
- Run full path:
  - `C:\Users\smk0101\AppData\Local\Programs\Ollama\ollama.exe`

### `npm` not recognized (no admin machine)

Use portable Node zip and set PATH for session.

### `WinError 10048` on backend start

Port already in use; kill old process via `netstat` + `taskkill`.

### Chat shows generic failure

- Check backend logs for `422`/`500`.
- Ensure backend is running and frontend `NEXT_PUBLIC_API_URL` is correct.
- Ensure Ollama server is running and model exists (`ollama list`).

---

## Git and Repository Workflow

Remote repo: [https://github.com/saikasireddy/NVA-Startups](https://github.com/saikasireddy/NVA-Startups)

Typical update flow:

```bat
git add .
git commit -m "Describe your change"
git push
```

---

## Hosting and Next Phases

### Phase 1: Stable local kiosk (zero cost)

- Keep backend + Ollama + index + DB on one local machine.
- Frontend runs locally.

### Phase 2: Split deployment

- Host frontend on Vercel.
- Keep backend/Ollama on an internal or on-prem machine.
- Lock CORS to frontend domain and add API-key auth.

### Phase 3: Production hardening

- Protect `/api/history/*` with admin auth.
- Add HTTPS reverse proxy (Caddy/Nginx).
- Move SQLite to Postgres if multi-user scale grows.
- Add process supervision and restart policies.
- Add backup policy for:
  - `backend/chat_history.db`
  - `backend/faiss_index`

---

## Suggested Immediate Next Tasks

1. Add backend API-key auth + frontend proxy key forwarding.
2. Lock CORS defaults for non-local environments.
3. Add `.env.example` files for backend/frontend.
4. Add startup scripts for repeatable launches.
5. Add a simple admin page in frontend to inspect session history endpoints.
