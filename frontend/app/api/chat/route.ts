import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type ChatMessage = {
  role: string;
  content: string;
};

export async function POST(req: NextRequest) {
  try {
    const { messages, sessionId } = (await req.json()) as {
      messages?: ChatMessage[];
      sessionId?: string;
    };
    const allMessages = messages ?? [];
    if (!sessionId) {
      return NextResponse.json({ error: "Missing sessionId." }, { status: 400 });
    }

    const lastUserMessage = [...allMessages].reverse().find((m) => m.role === "user");

    if (!lastUserMessage?.content) {
      return NextResponse.json({ error: "No user message provided." }, { status: 400 });
    }

    const simplifiedMessages: ChatMessage[] = allMessages
      .filter((m) => typeof m?.role === "string" && typeof m?.content === "string")
      .map((m) => ({
        role: m.role,
        content: m.content
      }));

    const response = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        messages: simplifiedMessages,
        session_id: sessionId
      })
    });

    if (!response.ok) {
      let details = "";
      try {
        details = await response.text();
      } catch {
        details = "Unable to read backend error body.";
      }
      return NextResponse.json({ error: details || "Backend chat request failed." }, { status: response.status });
    }

    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type": "text/plain; charset=utf-8"
      }
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Unexpected proxy error.",
        details: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    );
  }
}
