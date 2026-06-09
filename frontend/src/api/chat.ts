import { api, authHeaders, isMock } from "./client";
import { categoryLabel } from "@/lib/categories";

const BASE = import.meta.env.VITE_API_URL?.replace(/\/$/, "") || "/api";

export interface StreamChatOptions {
  message: string;
  sessionId: string;
  month?: string;
  lang: "vi" | "en";
  signal?: AbortSignal;
  onChunk: (text: string) => void;
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Stream a money-coach reply token-by-token.
 * Real backend: SSE over POST /chat (`data: {"text": "..."}` frames).
 * Mock: a data-aware canned reply streamed word by word.
 */
export async function streamChat(opts: StreamChatOptions): Promise<void> {
  if (isMock()) return streamMock(opts);

  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      message: opts.message,
      session_id: opts.sessionId,
      month: opts.month ?? null,
    }),
    signal: opts.signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Chat failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const payload = line.slice(5).trim();
      if (!payload || payload === "[DONE]") continue;
      try {
        const parsed = JSON.parse(payload);
        if (typeof parsed.text === "string") opts.onChunk(parsed.text);
      } catch {
        opts.onChunk(payload);
      }
    }
  }
}

export async function resetChat(sessionId: string): Promise<void> {
  if (isMock()) return;
  await fetch(`${BASE}/chat/reset`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({ session_id: sessionId }),
  }).catch(() => undefined);
}


async function streamMock({ message, month, lang, onChunk, signal }: StreamChatOptions) {
  const reply = await buildMockReply(message, month, lang);
  const tokens = reply.match(/\S+\s*/g) ?? [reply];
  for (const tok of tokens) {
    if (signal?.aborted) return;
    onChunk(tok);
    await delay(22);
  }
}

async function buildMockReply(
  message: string,
  month: string | undefined,
  lang: "vi" | "en",
): Promise<string> {
  const summary = await api.getSummary(month);
  const expenses = Object.entries(summary.by_category)
    .filter(([, v]) => v.total < 0)
    .sort((a, b) => a[1].total - b[1].total);
  const totalSpend = expenses.reduce((s, [, v]) => s + Math.abs(v.total), 0);
  const fmt = (n: number) =>
    new Intl.NumberFormat("vi-VN", {
      style: "currency",
      currency: "VND",
      maximumFractionDigits: 0,
    }).format(n);

  const top = expenses[0];
  const topLabel = top ? categoryLabel(top[0], lang) : "—";
  const topAmount = top ? Math.abs(top[1].total) : 0;
  const m = (message || "").toLowerCase();

  if (lang === "vi") {
    if (/tiết kiệm|tiet kiem|save/.test(m)) {
      return `Một vài gợi ý để tiết kiệm hơn:\n\n1. Danh mục "${topLabel}" đang chiếm phần lớn chi tiêu (${fmt(topAmount)}). Thử đặt hạn mức và theo dõi ở tab Phân tích.\n2. Rà soát các khoản đăng ký định kỳ — huỷ những dịch vụ ít dùng.\n3. Đặt mục tiêu tiết kiệm 10–20% thu nhập mỗi tháng và tự động chuyển khoản ngay khi nhận lương.\n\nBạn muốn mình giúp đặt ngân sách cho "${topLabel}" không?`;
    }
    if (/ngân sách|ngan sach|budget/.test(m)) {
      return `Dựa trên chi tiêu gần đây (tổng ${fmt(totalSpend)}), mình gợi ý ngân sách:\n\n• ${topLabel}: ${fmt(Math.round((topAmount * 0.9) / 1000) * 1000)}/tháng\n• Các danh mục còn lại: giữ ổn định và theo dõi hằng tuần.\n\nVào tab Phân tích để đặt hạn mức và nhận cảnh báo khi vượt nhé.`;
    }
    return `Trong kỳ này bạn đã chi khoảng ${fmt(totalSpend)}. Khoản lớn nhất là "${topLabel}" với ${fmt(topAmount)}. Bạn muốn mình phân tích sâu hơn một danh mục, hay gợi ý cách tối ưu chi tiêu?`;
  }

  if (/save|saving/.test(m)) {
    return `A few ways to save more:\n\n1. "${topLabel}" is your biggest category (${fmt(topAmount)}). Set a limit and track it on the Insights tab.\n2. Review recurring subscriptions — cancel what you rarely use.\n3. Aim to save 10–20% of income each month, auto-transferred on payday.\n\nWant me to help set a budget for "${topLabel}"?`;
  }
  if (/budget/.test(m)) {
    return `Based on recent spending (total ${fmt(totalSpend)}), here's a suggested budget:\n\n• ${topLabel}: ${fmt(Math.round((topAmount * 0.9) / 1000) * 1000)}/month\n• Keep other categories steady and review weekly.\n\nHead to Insights to set limits and get over-budget alerts.`;
  }
  return `This period you've spent about ${fmt(totalSpend)}. Your biggest category is "${topLabel}" at ${fmt(topAmount)}. Want a deeper look at a category, or tips to optimize?`;
}
