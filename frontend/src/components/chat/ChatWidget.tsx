import { useEffect, useRef, useState, forwardRef } from "react";
import {
  MessageCircle,
  X,
  RotateCcw,
  Send,
  Sparkles,
  Bot,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUi } from "@/context/ui";
import { useI18n } from "@/context/i18n";
import { useChat, type ChatMessage } from "@/hooks/useChat";
import { ChatMarkdown } from "./ChatMarkdown";
import type { StringKey } from "@/i18n/strings";
import { cn } from "@/lib/utils";

const SUGGESTIONS: StringKey[] = [
  "chat.suggest.1",
  "chat.suggest.2",
  "chat.suggest.3",
];

export function ChatWidget() {
  const { chatOpen, setChatOpen } = useUi();
  const { t } = useI18n();
  const { messages, streaming, send, reset } = useChat();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (chatOpen)
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, chatOpen]);

  useEffect(() => {
    if (!chatOpen) return;
    const tm = setTimeout(() => inputRef.current?.focus(), 120);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setChatOpen(false);
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(tm);
      window.removeEventListener("keydown", onKey);
    };
  }, [chatOpen, setChatOpen]);

  const submit = (text: string) => {
    send(text);
    setInput("");
  };

  return (
    <>
      {!chatOpen && (
        <button
          type="button"
          onClick={() => setChatOpen(true)}
          aria-label={t("chat.open")}
          className="fixed bottom-6 right-6 z-30 hidden size-14 place-items-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105 active:scale-95 lg:grid"
        >
          <MessageCircle className="size-6" />
        </button>
      )}

      {chatOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-slate-950/50 backdrop-blur-sm lg:hidden"
            onClick={() => setChatOpen(false)}
          />
          <div
            role="dialog"
            aria-label={t("chat.title")}
            className={cn(
              "bb-pop fixed z-40 flex flex-col overflow-hidden border border-border bg-card shadow-2xl",
              "inset-x-0 bottom-0 top-14 rounded-t-2xl",
              "lg:inset-auto lg:bottom-6 lg:right-6 lg:top-auto lg:h-[640px] lg:max-h-[calc(100dvh-3rem)] lg:w-[384px] lg:rounded-2xl",
            )}
          >
            <ChatHeader onReset={reset} onClose={() => setChatOpen(false)} />

            <div
              ref={scrollRef}
              className="scroll-thin flex-1 space-y-4 overflow-y-auto px-4 py-4"
            >
              {messages.length === 0 ? (
                <Greeting onPick={submit} />
              ) : (
                messages.map((m) => (
                  <Bubble key={m.id} message={m} streaming={streaming} />
                ))
              )}
            </div>

            <Composer
              ref={inputRef}
              value={input}
              onChange={setInput}
              onSubmit={submit}
              disabled={streaming}
            />
          </div>
        </>
      )}
    </>
  );
}

function ChatHeader({
  onReset,
  onClose,
}: {
  onReset: () => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-3 border-b border-border px-4 py-3">
      <span className="grid size-9 place-items-center rounded-full bg-primary text-primary-foreground">
        <Bot className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold leading-tight">{t("chat.title")}</p>
        <p className="text-xs text-muted-foreground">{t("chat.subtitle")}</p>
      </div>
      <Button
        variant="ghost"
        size="icon"
        onClick={onReset}
        aria-label={t("chat.reset")}
        title={t("chat.reset")}
      >
        <RotateCcw className="size-[18px]" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        onClick={onClose}
        aria-label={t("chat.close")}
      >
        <X className="size-5" />
      </Button>
    </div>
  );
}

function Greeting({ onPick }: { onPick: (text: string) => void }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center gap-4 px-2 py-6 text-center">
      <span className="grid size-12 place-items-center rounded-2xl bg-secondary text-primary">
        <Sparkles className="size-6" />
      </span>
      <p className="max-w-xs text-sm text-muted-foreground">
        {t("chat.greeting")}
      </p>
      <div className="flex w-full flex-col gap-2">
        {SUGGESTIONS.map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => onPick(t(key))}
            className="rounded-lg border border-border bg-card px-3 py-2 text-left text-sm transition-colors hover:border-ring hover:bg-secondary/60"
          >
            {t(key)}
          </button>
        ))}
      </div>
    </div>
  );
}

function Bubble({
  message,
  streaming,
}: {
  message: ChatMessage;
  streaming: boolean;
}) {
  const { t } = useI18n();
  const isUser = message.role === "user";
  const isPending = !isUser && streaming && !message.text;

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
          isUser
            ? "whitespace-pre-wrap rounded-br-sm bg-primary text-primary-foreground"
            : "rounded-bl-sm bg-secondary text-secondary-foreground",
        )}
        aria-live={isUser ? undefined : "polite"}
      >
        {isPending ? (
          <span className="flex items-center gap-1 py-0.5" aria-label={t("chat.thinking")}>
            <Dot /> <Dot /> <Dot />
          </span>
        ) : isUser ? (
          message.text
        ) : (
          <ChatMarkdown>{message.text}</ChatMarkdown>
        )}
      </div>
    </div>
  );
}

function Dot() {
  return (
    <span className="inline-block size-1.5 animate-pulse rounded-full bg-current opacity-60" />
  );
}

const Composer = forwardRef<
  HTMLTextAreaElement,
  {
    value: string;
    onChange: (v: string) => void;
    onSubmit: (v: string) => void;
    disabled: boolean;
  }
>(({ value, onChange, onSubmit, disabled }, ref) => {
  const { t } = useI18n();
  return (
    <div className="border-t border-border p-3">
      <div className="flex items-end gap-2">
        <textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSubmit(value);
            }
          }}
          placeholder={t("chat.placeholder")}
          className="scroll-thin max-h-28 min-h-10 flex-1 resize-none rounded-lg border border-input bg-card px-3 py-2 text-sm text-foreground shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button
          size="icon"
          aria-label={t("chat.send")}
          disabled={disabled || !value.trim()}
          onClick={() => onSubmit(value)}
        >
          <Send className="size-4" />
        </Button>
      </div>
      <p className="mt-1.5 px-1 text-[11px] text-muted-foreground">
        {t("chat.disclaimer")}
      </p>
    </div>
  );
});
Composer.displayName = "Composer";
