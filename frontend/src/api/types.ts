import type { Category } from "@/lib/categories";

export type TxnSource = "csv" | "pdf" | "manual";
export type Confidence = "high" | "medium" | "low" | string;

export interface Transaction {
  id: string;
  date: string;
  description: string;
  amount: number;
  category: Category;
  confidence?: Confidence;
  source?: TxnSource;
  /** AI was unsure (unmappable category or low confidence) — show a review badge. */
  needs_review?: boolean;
}

/** Payload for creating a transaction (POST /transaction). */
export interface TransactionInput {
  date: string;
  description: string;
  amount: number;
  category?: Category;
  source?: TxnSource;
}

export interface CategoryBucket {
  total: number;
  count: number;
}

/** GET /summary response (mirrors the FastAPI handler's richer shape). */
export interface Summary {
  month?: string | null;
  total_spend: number;
  by_category: Record<string, CategoryBucket>;
  top_3_drivers: { category: string; total: number; count: number }[];
  daily_trends: { date: string; amount: number }[];
}

/** POST /upload (CSV) response. */
export interface UploadResult {
  filename?: string;
  rows_parsed: number;
  rows_inserted: number;
  transactions: Transaction[];
  /** Subtle cost hint surfaced in the UI ("≈ $0.005"). */
  ai_cost_usd?: number;
  cost_estimate_usd?: number;
  tokens?: { input: number; output: number };
  duplicates_skipped?: {
    row: number;
    description?: string;
    amount?: number;
    date?: string;
    matched_existing_id?: string | null;
  }[];
  summary?: {
    total_rows: number;
    new_saved: number;
    duplicates_skipped: number;
    needs_review?: number;
    errors: number;
  };
  /** Set when the budget guard degraded this upload to rule-based classification. */
  ai_warning?: { type: string; message: string } | null;
}

/** One row of the classification audit trail (GET /transaction/{id}/audit). */
export interface AuditEntry {
  source: string;
  category: string;
  confidence?: string;
  needs_review?: boolean;
  prompt_version?: string;
  model_id?: string;
  ts?: string;
}

export interface AuditResponse {
  transaction_id: string;
  audit: AuditEntry[];
}

/** Async upload job (POST /enqueue → poll GET /job-status/{id}). */
export interface JobStatus {
  job_id: string;
  status: "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED" | "NOT_FOUND";
  rows_inserted?: number;
  error?: string;
  message?: string;
}

export interface ReceiptItem {
  name: string;
  amount: number;
}

/** POST /upload-pdf response — editable extracted fields. */
export interface ReceiptExtraction {
  merchant: string;
  date: string;
  amount: number;
  items: ReceiptItem[];
  category: Category;
  ai_cost_usd?: number;
  warnings?: { type: string; message: string }[];
}

/** Existing-upload info returned with a 409 duplicate_file. */
export interface DuplicateFileInfo {
  id?: string;
  filename?: string;
  uploaded_at?: string;
  transaction_count?: number;
  file_type?: string;
}

/** Result of an upload attempt — either processed, or a duplicate to resolve. */
export type UploadOutcome =
  | { kind: "ok"; result: UploadResult }
  | { kind: "duplicate"; info: DuplicateFileInfo; message: string };

export type UploadForce = "append" | "replace";

/** Soft duplicate warning on manual entry. */
export interface DuplicateWarning {
  type: string;
  message: string;
  matching_transactions?: Transaction[];
}

/** Result of a manual create — saved, or held back with a warning. */
export type CreateOutcome =
  | { kind: "saved"; transaction: Transaction }
  | { kind: "warning"; warning: DuplicateWarning };

/** GET /budgets response (used on Insights). */
export interface BudgetStatus {
  category: string;
  limit: number;
  spent: number;
  remaining: number;
  percent: number;
  exceeded: boolean;
}

export interface BudgetsResponse {
  budgets: Record<string, number>;
  status: BudgetStatus[];
  alerts: BudgetStatus[];
}
