import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat, resetChat } from "@/api/chat";
import { useUi } from "@/context/ui";
import { useI18n } from "@/context/i18n";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}

const STORE_KEY = "budgetbot.chat";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${performance.now()}`;
}

interface Persisted {
  sessionId: string;
  messages: ChatMessage[];
}

function load(): Persisted {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (raw) return JSON.parse(raw) as Persisted;
  } catch {
  }
  return { sessionId: newId(), messages: [] };
}

export function useChat() {
  const { month } = useUi();
  const { t, lang } = useI18n();
  const [{ sessionId, messages }, setState] = useState<Persisted>(load);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    localStorage.setItem(STORE_KEY, JSON.stringify({ sessionId, messages }));
  }, [sessionId, messages]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || streaming) return;

      const userMsg: ChatMessage = { id: newId(), role: "user", text: trimmed };
      const assistantId = newId();
      setState((s) => ({
        ...s,
        messages: [
          ...s.messages,
          userMsg,
          { id: assistantId, role: "assistant", text: "" },
        ],
      }));
      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const appendChunk = (chunk: string) =>
        setState((s) => ({
          ...s,
          messages: s.messages.map((m) =>
            m.id === assistantId ? { ...m, text: m.text + chunk } : m,
          ),
        }));

      try {
        await streamChat({
          message: trimmed,
          sessionId,
          month,
          lang,
          signal: controller.signal,
          onChunk: appendChunk,
        });
      } catch {
        setState((s) => ({
          ...s,
          messages: s.messages.map((m) =>
            m.id === assistantId && !m.text
              ? { ...m, text: t("chat.error") }
              : m,
          ),
        }));
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [streaming, sessionId, month, lang, t],
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    resetChat(sessionId);
    setState({ sessionId: newId(), messages: [] });
    setStreaming(false);
  }, [sessionId]);

  return { messages, streaming, send, reset };
}
