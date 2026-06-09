import type {
  Transaction,
  TransactionInput,
  Summary,
  UploadResult,
  ReceiptExtraction,
  BudgetsResponse,
  UploadOutcome,
  UploadForce,
  CreateOutcome,
  AuditResponse,
  JobStatus,
} from "./types";
import type { Category } from "@/lib/categories";
import { MockStore } from "@/mock/data";
import { currentMonth } from "@/lib/format";

const BASE = import.meta.env.VITE_API_URL?.replace(/\/$/, "") || "/api";
const USER_KEY = "budgetbot.userId";
const MOCK_KEY = "budgetbot.useMock";

export function getUserId(): string {
  return localStorage.getItem(USER_KEY) || "demo-user";
}
export function setUserId(id: string): void {
  localStorage.setItem(USER_KEY, id.trim() || "demo-user");
}

let _authToken: string | null = null;
export function setAuthToken(token: string | null): void {
  _authToken = token;
}

/** Identity headers for every request (X-User-Id + Cognito Bearer when present). */
export function authHeaders(): Record<string, string> {
  return {
    "X-User-Id": getUserId(),
    ...(_authToken ? { Authorization: `Bearer ${_authToken}` } : {}),
  };
}

/** Files larger than this go through the async pipeline (/enqueue + poll). */
export const ASYNC_MIN_BYTES = 1_000_000;
export function shouldUseAsync(file: File): boolean {
  return file.size > ASYNC_MIN_BYTES;
}

/** Mock mode is on when the env default is true, unless the user overrode it. */
export function isMock(): boolean {
  const override = localStorage.getItem(MOCK_KEY);
  if (override !== null) return override === "true";
  return (import.meta.env.VITE_USE_MOCK ?? "true") !== "false";
}
export function setMock(on: boolean): void {
  localStorage.setItem(MOCK_KEY, String(on));
}

let _store: MockStore | null = null;
function store(): MockStore {
  if (!_store) _store = new MockStore(currentMonth());
  return _store;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new ApiError(res.status, detail || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const api = {
  async health(): Promise<{ status: string; require_auth?: boolean }> {
    if (isMock()) return { status: "ok", require_auth: false };
    return http("/health");
  },

  async listTransactions(month?: string): Promise<Transaction[]> {
    if (isMock()) return store().list(month);
    const params = new URLSearchParams({ page: "1", page_size: "500" });
    if (month) params.set("month", month);
    const data = await http<{ transactions: Transaction[] }>(
      `/transactions?${params.toString()}`,
    );
    return data.transactions;
  },

  /**
   * Fetch the COMPLETE transaction history (every page). The dashboard
   * aggregates spend across the current month, the previous month, and the
   * last 6 months client-side — a single page_size-capped call silently
   * undercounts the moment a user has more than one page of data.
   */
  async listAllTransactions(month?: string): Promise<Transaction[]> {
    if (isMock()) return store().list(month);
    const PAGE = 500;
    const all: Transaction[] = [];
    for (let page = 1; page <= 200; page++) {
      const params = new URLSearchParams({ page: String(page), page_size: String(PAGE) });
      if (month) params.set("month", month);
      const data = await http<{ transactions: Transaction[] }>(
        `/transactions?${params.toString()}`,
      );
      all.push(...data.transactions);
      if (data.transactions.length < PAGE) break;
    }
    return all;
  },

  async getSummary(month?: string): Promise<Summary> {
    if (isMock()) return store().summary(month);
    const q = month ? `?month=${month}` : "";
    return http(`/summary${q}`);
  },

  /** Force-save (skips the soft duplicate warning). */
  async createTransaction(input: TransactionInput): Promise<Transaction> {
    if (isMock()) return store().create(input);
    const res = await http<{ transaction: Transaction }>("/transaction?confirm=true", {
      method: "POST",
      body: JSON.stringify(input),
    });
    return res.transaction;
  },

  /** Create with the soft dedup check — may return a warning instead of saving. */
  async createTransactionChecked(input: TransactionInput): Promise<CreateOutcome> {
    if (isMock()) return store().createChecked(input);
    const res = await http<{
      transaction: Transaction;
      saved: boolean;
      warning?: { type: string; message: string; matching_transactions?: Transaction[] };
    }>("/transaction", { method: "POST", body: JSON.stringify(input) });
    if (res.saved) return { kind: "saved", transaction: res.transaction };
    return {
      kind: "warning",
      warning: res.warning ?? { type: "possible_duplicate", message: "" },
    };
  },

  async updateCategory(id: string, category: Category): Promise<Transaction> {
    if (isMock()) return store().update(id, { category });
    const res = await http<{ transaction: Transaction }>(`/transaction/${id}`, {
      method: "PUT",
      body: JSON.stringify({ category }),
    });
    return res.transaction;
  },

  async deleteTransaction(id: string): Promise<void> {
    if (isMock()) return store().remove(id);
    await http(`/transaction/${id}`, { method: "DELETE" });
  },

  /** Classification audit trail — why a transaction got its category. */
  async getAudit(id: string): Promise<AuditResponse> {
    if (isMock()) return store().getAudit(id);
    return http<AuditResponse>(`/transaction/${id}/audit`);
  },

  async clearAll(): Promise<void> {
    if (isMock()) return store().clearAll();
    await http(`/transactions`, { method: "DELETE" });
  },

  async uploadCsv(file: File, force?: UploadForce): Promise<UploadOutcome> {
    if (isMock()) {
      const text = /\.csv$/i.test(file.name) ? await file.text() : "";
      return store().uploadCsv(text, force, file.name);
    }
    const form = new FormData();
    form.append("file", file);
    const q = force ? `?force=${force}` : "";
    const res = await fetch(`${BASE}/upload${q}`, {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });
    if (res.status === 409) {
      const body = await res.json().catch(() => ({}));
      return {
        kind: "duplicate",
        info: body.existing_upload ?? {},
        message: body.message ?? "File đã được tải lên trước đó.",
      };
    }
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new ApiError(res.status, detail || res.statusText);
    }
    return { kind: "ok", result: (await res.json()) as UploadResult };
  },

  /** Async import for large files: enqueue then poll getJobStatus. */
  async enqueueCsv(file: File): Promise<JobStatus> {
    if (isMock()) return store().enqueueCsv(file);
    const form = new FormData();
    form.append("file", file);
    return http<JobStatus>("/enqueue", { method: "POST", body: form });
  },

  async getJobStatus(jobId: string): Promise<JobStatus> {
    if (isMock()) return store().getJobStatus(jobId);
    return http<JobStatus>(`/job-status/${encodeURIComponent(jobId)}`);
  },

  async uploadPdf(file: File): Promise<ReceiptExtraction> {
    if (isMock()) return store().uploadPdf(file.name);
    const form = new FormData();
    form.append("file", file);
    return http("/upload-pdf", { method: "POST", body: form });
  },

  async getBudgets(month?: string): Promise<BudgetsResponse> {
    if (isMock()) return store().getBudgets(month);
    const q = month ? `?month=${month}` : "";
    return http(`/budgets${q}`);
  },

  async setBudget(category: string, amount: number): Promise<void> {
    if (isMock()) return store().setBudget(category, amount);
    await http(`/budgets`, {
      method: "POST",
      body: JSON.stringify({ category, amount }),
    });
  },
};
