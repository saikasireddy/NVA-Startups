# NVA Mentoring Startups Guide Chatbot

Production-style, zero-cost RAG assistant with a decoupled architecture:

- `backend/`: FastAPI + LangChain LCEL + FAISS (disk-backed) + ChatOllama + SQLite memory + SlowAPI + Phoenix tracing
- `frontend/`: Next.js App Router + Tailwind + Vercel AI SDK (`useChat`) with streaming UI

The assistant answers using `Mentoring Startups GuideF.docx`.

## Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com/) installed locally

## 1) Backend setup

```bash
cd backend
python -m venv .venv
```

Activate venv:

- Windows PowerShell: `.\.venv\Scripts\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## 2) Build FAISS index first (decoupled ETL)

Run from `backend/`:

```bash
python ingest.py
```

This creates `backend/faiss_index`.  
The API server will only load this index and will not rebuild it.

## 3) Start Ollama (local LLM)

Terminal A:

```bash
ollama serve
```

Terminal B (first-time pull):

```bash
ollama run llama3
```

## 4) Start Phoenix (local observability)

In a separate terminal:

```bash
phoenix serve
```

Default Phoenix UI is usually available at [http://127.0.0.1:6006](http://127.0.0.1:6006).

## 5) Run FastAPI backend

From `backend/`:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Backend behavior

- Uses `SQLChatMessageHistory` with `sqlite:///chat_history.db`
- Stores conversation by `session_id`
- Prunes memory to last 5 user/assistant turns for prompt context
- Rate limits `POST /api/chat` to `10 requests/minute` per IP
- Streams tokens using `StreamingResponse`

### Backend env vars (optional)

- `DOCX_PATH`: path to DOCX guide
- `FAISS_INDEX_DIR`: path to FAISS index directory (default `backend/faiss_index`)
- `FRONTEND_URL`: allowed origin when `CORS_ALLOW_ALL=false`
- `CORS_ALLOW_ALL`: default `true`

## 6) Run Next.js frontend

From `frontend/`:

```bash
npm install
npm run dev
```

`frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Open [http://localhost:3000](http://localhost:3000).

## API Contract (backend)

- `POST /api/chat` (streaming text response)
  - Request JSON:
    ```json
    {
      "session_id": "b9e0e2db-1d1f-4eec-a9be-cfbbf4a9d963",
      "messages": [
        { "role": "user", "content": "How should mentors handle founder conflict?" }
      ]
    }
    ```
  - Response: streamed plain text tokens.

- `GET /api/history/{session_id}`
  - Returns full persisted conversation for one session.
  - Example response:
    ```json
    {
      "session_id": "b9e0e2db-1d1f-4eec-a9be-cfbbf4a9d963",
      "message_count": 6,
      "messages": [
        { "role": "user", "content": "..." },
        { "role": "assistant", "content": "..." }
      ]
    }
    ```

- `GET /api/history/sessions?page=1&page_size=20`
  - Paginated list of sessions (sorted by most recent activity), with message counts and first-message preview.
  - Example response:
    ```json
    {
      "page": 1,
      "page_size": 20,
      "total_sessions": 12,
      "sessions": [
        {
          "session_id": "b9e0e2db-1d1f-4eec-a9be-cfbbf4a9d963",
          "message_count": 8,
          "preview": "How do I set mentor milestones?"
        }
      ]
    }
    ```
