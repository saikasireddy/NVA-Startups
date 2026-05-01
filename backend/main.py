import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import create_engine, text

from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, get_buffer_string
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import Runnable, RunnablePassthrough


SYSTEM_PROMPT_TEMPLATE = """
You are an official NVA Mentor. Answer questions based ONLY on the provided context.
In this assistant, "NVA" always means "New Venture Accelerator" (not any other acronym).
Never redefine NVA as a different term.
If the user asks about topics outside of startups, gracefully decline.
If the question is startup-related but not answered directly, infer practical guidance from closely related context in the guide and clearly say it is an inferred recommendation.
Only say you do not know when the guide context is truly unrelated.

Context:
{context}

Chat History:
{history}

Question:
{question}

Answer:
"""


class ChatRequest(BaseModel):
    messages: list[dict[str, str]] = Field(default_factory=list)
    session_id: str = Field(..., min_length=1)


def build_chain(vectorstore: FAISS) -> Runnable[Any, str]:
    retriever_k = int(os.getenv("RETRIEVER_K", "4"))
    retriever = vectorstore.as_retriever(search_kwargs={"k": retriever_k})
    prompt = PromptTemplate(
        input_variables=["context", "history", "question"],
        template=SYSTEM_PROMPT_TEMPLATE,
    )

    # Ensure Ollama is running locally and model is pulled:
    # ollama run llama3
    llm_model = os.getenv("OLLAMA_MODEL", "llama3")
    llm_temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
    llm_num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "220"))
    llm_num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "2048"))

    llm = ChatOllama(
        model=llm_model,
        temperature=llm_temperature,
        num_predict=llm_num_predict,
        num_ctx=llm_num_ctx,
    )

    def format_docs(retrieved_docs: list[Any]) -> str:
        return "\n\n".join(doc.page_content for doc in retrieved_docs)

    def format_history(history_value: Any) -> str:
        if isinstance(history_value, list):
            return get_buffer_string(history_value)
        return str(history_value or "")

    rag_chain: Runnable[Any, str] = (
        RunnablePassthrough.assign(
            context=lambda x: format_docs(retriever.invoke(x["question"])),
            history=lambda x: format_history(x.get("history", [])),
        )
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Optional local Phoenix tracing (non-blocking if unavailable).
    try:
        from phoenix.otel import register

        register(auto_instrument=True)
    except Exception:
        pass

    backend_dir = Path(__file__).resolve().parent
    index_dir = Path(os.getenv("FAISS_INDEX_DIR", str(backend_dir / "faiss_index")))

    if not index_dir.exists():
        raise FileNotFoundError(
            f"FAISS index not found at '{index_dir}'. Run 'python ingest.py' in backend first."
        )

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = FAISS.load_local(
        folder_path=str(index_dir),
        embeddings=embeddings,
        allow_dangerous_deserialization=True,
    )
    app.state.chain = build_chain(vectorstore)
    yield


app = FastAPI(
    title="NVA Mentoring RAG API",
    version="1.0.0",
    lifespan=lifespan,
)
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
allow_all_origins = os.getenv("CORS_ALLOW_ALL", "true").lower() == "true"
allowed_origins = ["*"] if allow_all_origins else [frontend_url]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def get_sql_history(session_id: str) -> SQLChatMessageHistory:
    return SQLChatMessageHistory(
        session_id=session_id,
        connection_string="sqlite:///chat_history.db",
    )


def get_db_engine():
    return create_engine("sqlite:///chat_history.db")


def prune_to_last_interactions(messages: list[BaseMessage], max_turns: int = 5) -> list[BaseMessage]:
    trimmed = messages[-(max_turns * 2) :]
    return trimmed


@app.get("/api/history/sessions")
def list_history_sessions(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="page_size must be between 1 and 100")

    offset = (page - 1) * page_size
    engine = get_db_engine()

    with engine.connect() as conn:
        total_sessions = conn.execute(
            text(
                """
                SELECT COUNT(*) AS total
                FROM (
                  SELECT session_id
                  FROM message_store
                  GROUP BY session_id
                ) s
                """
            )
        ).scalar_one()

        rows = conn.execute(
            text(
                """
                SELECT
                  m.session_id,
                  MIN(m.id) AS first_message_id,
                  MAX(m.id) AS last_message_id,
                  COUNT(*) AS message_count
                FROM message_store m
                GROUP BY m.session_id
                ORDER BY last_message_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": page_size, "offset": offset},
        ).mappings().all()

        sessions: list[dict[str, Any]] = []
        for row in rows:
            preview = conn.execute(
                text(
                    """
                    SELECT message
                    FROM message_store
                    WHERE session_id = :session_id
                    ORDER BY id ASC
                    LIMIT 1
                    """
                ),
                {"session_id": row["session_id"]},
            ).scalar_one_or_none()

            sessions.append(
                {
                    "session_id": row["session_id"],
                    "message_count": int(row["message_count"]),
                    "preview": preview or "",
                }
            )

    return {
        "page": page,
        "page_size": page_size,
        "total_sessions": int(total_sessions),
        "sessions": sessions,
    }


@app.get("/api/history/{session_id}")
def get_history_by_session(session_id: str) -> dict[str, Any]:
    history_store = get_sql_history(session_id)
    messages = history_store.messages
    if not messages:
        raise HTTPException(status_code=404, detail="No history found for session_id")

    serialized: list[dict[str, str]] = []
    for message in messages:
        role = "assistant"
        if isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        serialized.append({"role": role, "content": str(message.content)})

    return {
        "session_id": session_id,
        "message_count": len(serialized),
        "messages": serialized,
    }


@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat(request: Request, payload: ChatRequest) -> Any:
    chain = getattr(app.state, "chain", None)
    if chain is None:
        raise HTTPException(status_code=503, detail="RAG chain is not ready.")

    user_message = ""
    for message in reversed(payload.messages):
        if message.get("role") == "user" and message.get("content", "").strip():
            user_message = message["content"].strip()
            break
    if not user_message:
        raise HTTPException(status_code=400, detail="No user message provided.")

    history_store = get_sql_history(payload.session_id)
    max_turns = int(os.getenv("MAX_HISTORY_TURNS", "3"))
    pruned_messages = prune_to_last_interactions(history_store.messages, max_turns=max_turns)
    history_text = get_buffer_string(pruned_messages)
    history_store.add_user_message(user_message)

    async def stream_response() -> AsyncGenerator[str, None]:
        chunks: list[str] = []
        try:
            async for token in chain.astream({"question": user_message, "history": history_text}):
                token_text = str(token)
                if token_text:
                    chunks.append(token_text)
                    yield token_text
            final_answer = "".join(chunks).strip()
            if final_answer:
                history_store.add_ai_message(final_answer)
            else:
                fallback = "I could not find a reliable answer in the guide."
                history_store.add_ai_message(fallback)
                yield fallback
        except Exception as exc:
            error_message = (
                "I ran into an internal error while generating the response. "
                "Please try again."
            )
            history_store.add_ai_message(error_message)
            yield f"\n\n[Error: {exc}]"

    try:
        return StreamingResponse(stream_response(), media_type="text/plain; charset=utf-8")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat generation failed: {exc}") from exc
