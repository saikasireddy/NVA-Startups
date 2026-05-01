"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useChat } from "@ai-sdk/react";
import { v4 as uuidv4 } from "uuid";

export default function HomePage() {
  const [sessionId, setSessionId] = useState("");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setSessionId(uuidv4());
  }, []);

  const { messages, input, handleInputChange, handleSubmit, isLoading, error } = useChat({
    api: "/api/chat",
    streamProtocol: "text",
    body: { sessionId }
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!input.trim() || !sessionId) return;
    handleSubmit(event);
  };

  const quickPrompts = useMemo(
    () => [
      "How should mentors structure weekly founder check-ins?",
      "What should mentors do when co-founders disagree?",
      "How can I set milestone-based accountability for startups?"
    ],
    []
  );

  const useQuickPrompt = (prompt: string) => {
    if (!sessionId || isLoading) return;
    handleInputChange({
      target: { value: prompt }
    } as ChangeEvent<HTMLInputElement>);
  };

  const errorText = error?.message?.includes("429")
    ? "Rate limit reached (10 requests/minute). Please wait and try again."
    : "Chat request failed. Verify backend, Ollama, and FAISS ingest are running.";

  return (
    <main className="mx-auto flex h-screen w-full max-w-6xl flex-col px-4 py-6">
      <header className="mb-4 rounded-2xl bg-gradient-to-r from-slate-950 to-slate-800 p-6 text-white shadow-lg">
        <h1 className="text-2xl font-semibold md:text-3xl">New Venture Accelerator</h1>
        <p className="mt-1 text-sm text-slate-200 md:text-base">
          Mentoring Startups Guide Assistant
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-emerald-200">
            Local RAG
          </span>
          <span className="rounded-full bg-sky-500/20 px-3 py-1 text-sky-200">
            Ollama Llama3
          </span>
          <span className="rounded-full bg-violet-500/20 px-3 py-1 text-violet-200">
            Session: {sessionId ? sessionId.slice(0, 8) : "initializing..."}
          </span>
        </div>
      </header>

      <section className="flex-1 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col justify-center">
            <p className="mb-4 text-center text-slate-600">
              Ask a question about mentoring startups to begin.
            </p>
            <div className="mx-auto grid w-full max-w-3xl gap-2 md:grid-cols-3">
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => useQuickPrompt(prompt)}
                  className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs text-slate-700 transition hover:border-blue-300 hover:bg-blue-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                  message.role === "user"
                    ? "ml-auto bg-blue-600 text-white"
                    : "mr-auto border border-slate-200 bg-slate-50 text-slate-900"
                }`}
              >
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide opacity-80">
                  {message.role === "user" ? "You" : "NVA Assistant"}
                </p>
                {message.content}
              </div>
            ))}
            {isLoading && (
              <div className="mr-auto max-w-[85%] rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 shadow-sm">
                Thinking...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </section>

      <form
        onSubmit={onSubmit}
        className="mt-4 flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm"
      >
        <input
          className="flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
          value={input}
          onChange={handleInputChange}
          placeholder="Ask about mentoring startups..."
        />
        <button
          type="submit"
          disabled={isLoading || !sessionId}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-blue-400"
        >
          Send
        </button>
      </form>

      {error && (
        <p className="mt-2 text-sm text-red-600">{errorText}</p>
      )}
    </main>
  );
}
