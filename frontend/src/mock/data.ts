import type {
  Transaction,
  TransactionInput,
  Summary,
  UploadResult,
  UploadOutcome,
  CreateOutcome,
  ReceiptExtraction,
  BudgetsResponse,
  BudgetStatus,
  AuditResponse,
  JobStatus,
} from "@/api/types";
import { suggestCategory, type Category } from "@/lib/categories";
import { shiftMonth, currentMonth } from "@/lib/format";

/** date-less fingerprint mirroring the backend (amount + normalised desc). */
function fingerprint(amount: number, description: string): string {
  const norm = description
    .toLowerCase()
    .replace(/\*\d+|#\d+|-\d{6,}/g, " ")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter(Boolean)
    .sort()
    .join(" ");
  return `${Math.round(amount)}|${norm}`;
}

function daysApart(a: string, b: string): number {
  const da = new Date(a).getTime();
  const db = new Date(b).getTime();
  if (Number.isNaN(da) || Number.isNaN(db)) return a.slice(0, 10) === b.slice(0, 10) ? 0 : 99;
  return Math.abs(Math.round((da - db) / 86_400_000));
}

/**
 * In-memory mock backend. Mirrors the FastAPI contract closely enough that the
 * whole UI is interactive on first run with no server. Toggle via VITE_USE_MOCK.
 */

let counter = 0;
const nextId = () => `t${++counter}`;

interface Seed {
  day: number;
  desc: string;
  amount: number;
  category: Category;
  source?: Transaction["source"];
  review?: boolean;
}

const MONTH_TEMPLATE: Seed[] = [
  { day: 1, desc: "Lương tháng", amount: 28_000_000, category: "Salary", source: "csv" },
  { day: 2, desc: "Highlands Coffee - Bùi Viện", amount: -65_000, category: "Food", source: "csv" },
  { day: 3, desc: "Grab tới văn phòng", amount: -48_000, category: "Transport", source: "manual" },
  { day: 4, desc: "Netflix Premium", amount: -260_000, category: "Entertainment", source: "csv" },
  { day: 5, desc: "Shopee - đồ gia dụng", amount: -450_000, category: "Shopping", source: "csv" },
  { day: 7, desc: "EVN tiền điện", amount: -850_000, category: "Bills", source: "csv" },
  { day: 9, desc: "Cơm trưa văn phòng", amount: -55_000, category: "Food", source: "manual" },
  { day: 11, desc: "CGV Vincom - 2 vé", amount: -240_000, category: "Entertainment", source: "csv" },
  { day: 12, desc: "Pharmacity - vitamin", amount: -185_000, category: "Health", source: "pdf" },
  { day: 14, desc: "Spotify Family", amount: -59_000, category: "Entertainment", source: "csv" },
  { day: 15, desc: "Be - sân bay", amount: -210_000, category: "Transport", source: "manual" },
  { day: 17, desc: "Lazada - áo khoác", amount: -520_000, category: "Shopping", source: "csv" },
  { day: 19, desc: "Bún bò Huế", amount: -70_000, category: "Food", source: "manual" },
  { day: 21, desc: "Internet FPT", amount: -250_000, category: "Bills", source: "csv" },
  { day: 23, desc: "Chuyển khoản tiết kiệm", amount: -3_000_000, category: "Transfer", source: "manual" },
  { day: 24, desc: "TT HD 8829100 NDUNG", amount: -1_290_000, category: "Other", source: "csv", review: true },
  { day: 25, desc: "Trà sữa Phúc Long", amount: -68_000, category: "Food", source: "csv" },
  { day: 27, desc: "Xăng xe", amount: -120_000, category: "Transport", source: "csv" },
  { day: 28, desc: "Long Châu - thuốc cảm", amount: -95_000, category: "Health", source: "pdf" },
];

function buildSeed(currentMonth: string): Transaction[] {
  const txns: Transaction[] = [];
  for (let back = 5; back >= 0; back--) {
    const month = shiftMonth(currentMonth, -back);
    const variance = 1 + (((back * 37) % 20) - 10) / 100;
    for (const s of MONTH_TEMPLATE) {
      const amount =
        s.category === "Salary"
          ? s.amount
          : Math.round((s.amount * variance) / 1000) * 1000;
      txns.push({
        id: nextId(),
        date: `${month}-${String(s.day).padStart(2, "0")}`,
        description: s.desc,
        amount,
        category: s.category,
        confidence: s.review ? "low" : "high",
        source: s.source ?? "csv",
        needs_review: back === 0 ? !!s.review : false,
      });
    }
  }
  return txns;
}

function aggregate(rows: Transaction[], month?: string): Summary {
  const scoped = month ? rows.filter((t) => t.date.startsWith(month)) : rows;
  const by_category: Summary["by_category"] = {};
  for (const t of scoped) {
    const b = (by_category[t.category] ??= { total: 0, count: 0 });
    b.total += t.amount;
    b.count += 1;
  }
  const total_spend = scoped.reduce((s, t) => s + t.amount, 0);
  const expenses = Object.entries(by_category)
    .filter(([, v]) => v.total < 0)
    .sort((a, b) => a[1].total - b[1].total);
  const daily: Record<string, number> = {};
  for (const t of scoped) {
    if (t.amount < 0) daily[t.date] = (daily[t.date] ?? 0) + Math.abs(t.amount);
  }
  return {
    month: month ?? null,
    total_spend,
    by_category,
    top_3_drivers: expenses.slice(0, 3).map(([category, v]) => ({
      category,
      total: v.total,
      count: v.count,
    })),
    daily_trends: Object.entries(daily)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, amount]) => ({ date, amount })),
  };
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export class MockStore {
  private rows: Transaction[];
  private budgets: Record<string, number> = {
    Food: 2_500_000,
    Shopping: 1_500_000,
    Transport: 1_200_000,
    Entertainment: 800_000,
  };

  constructor(currentMonth: string) {
    this.rows = buildSeed(currentMonth);
  }

  async list(month?: string): Promise<Transaction[]> {
    await delay(120);
    const rows = month
      ? this.rows.filter((t) => t.date.startsWith(month))
      : this.rows;
    return [...rows].sort((a, b) => b.date.localeCompare(a.date));
  }

  async summary(month?: string): Promise<Summary> {
    await delay(120);
    return aggregate(this.rows, month);
  }

  async create(input: TransactionInput): Promise<Transaction> {
    await delay(150);
    const txn: Transaction = {
      id: nextId(),
      date: input.date,
      description: input.description,
      amount: input.amount,
      category: input.category ?? suggestCategory(input.description, input.amount),
      confidence: "high",
      source: input.source ?? "manual",
    };
    this.rows.push(txn);
    return txn;
  }

  async update(id: string, patch: Partial<Transaction>): Promise<Transaction> {
    await delay(120);
    const t = this.rows.find((r) => r.id === id);
    if (!t) throw new Error("Không tìm thấy giao dịch");
    Object.assign(t, patch);
    return t;
  }

  async remove(id: string): Promise<void> {
    await delay(120);
    this.rows = this.rows.filter((r) => r.id !== id);
  }

  async clearAll(): Promise<void> {
    await delay(120);
    this.rows = [];
  }

  private fileHashes = new Map<string, { count: number; at: string; name: string }>();

  private hashText(text: string): string {
    let h = 5381;
    for (let i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) | 0;
    return String(h >>> 0);
  }

  async uploadCsv(
    text: string,
    force?: "append" | "replace",
    filename = "statement.csv",
  ): Promise<UploadOutcome> {
    await delay(400);
    if (!text.trim()) {
      const today = currentMonth();
      text =
        `${today}-02,Highlands Coffee,-65000\n` +
        `${today}-03,Grab,-48000\n` +
        `${today}-05,Shopee,-450000\n` +
        `${today}-06,EVN tiền điện,-820000\n` +
        filename;
    }

    const hash = this.hashText(text);
    const prior = this.fileHashes.get(hash);
    if (prior && !force) {
      return {
        kind: "duplicate",
        info: {
          filename: prior.name,
          uploaded_at: prior.at,
          transaction_count: prior.count,
          file_type: /\.(xlsx|xls)$/i.test(filename) ? "excel" : "csv",
        },
        message: `File này đã tải lên lúc ${prior.at.slice(0, 16).replace("T", " ")} (${prior.count} giao dịch).`,
      };
    }

    const lines = text.split(/\r?\n/).filter((l) => l.trim());
    const parsed: { date: string; description: string; amount: number }[] = [];
    for (const line of lines) {
      const cells = line.split(",").map((c) => c.trim());
      if (cells.length < 3) continue;
      if (/date/i.test(cells[0]) && /amount/i.test(cells[2])) continue;
      const amount = Number(cells[2].replace(/[^\d.-]/g, ""));
      if (!cells[0] || Number.isNaN(amount)) continue;
      parsed.push({ date: cells[0], description: cells[1], amount });
    }

    const saved: Transaction[] = [];
    const duplicates: NonNullable<UploadResult["duplicates_skipped"]> = [];
    const seen: { fp: string; date: string }[] = [];
    parsed.forEach((row, i) => {
      const fp = fingerprint(row.amount, row.description);
      const batchHit = seen.find((s) => s.fp === fp && daysApart(s.date, row.date) <= 1);
      const dbHit = this.rows.find(
        (t) => fingerprint(t.amount, t.description) === fp && daysApart(t.date, row.date) <= 1,
      );
      if (batchHit || dbHit) {
        duplicates.push({
          row: i + 1, description: row.description, amount: row.amount, date: row.date,
          matched_existing_id: dbHit?.id ?? null,
        });
        return;
      }
      seen.push({ fp, date: row.date });
      const txn: Transaction = {
        id: nextId(), date: row.date, description: row.description, amount: row.amount,
        category: suggestCategory(row.description, row.amount), confidence: "high", source: "csv",
      };
      this.rows.push(txn);
      saved.push(txn);
    });

    this.fileHashes.set(hash, { count: saved.length, at: new Date().toISOString(), name: filename });

    const result: UploadResult = {
      rows_parsed: parsed.length,
      rows_inserted: saved.length,
      transactions: saved,
      ai_cost_usd: Math.max(0.001, saved.length * 0.00011),
      cost_estimate_usd: Math.max(0.001, saved.length * 0.00011),
      tokens: { input: saved.length * 70, output: saved.length * 20 },
      duplicates_skipped: duplicates,
      summary: {
        total_rows: parsed.length,
        new_saved: saved.length,
        duplicates_skipped: duplicates.length,
        errors: 0,
      },
    };
    return { kind: "ok", result };
  }

  async createChecked(input: TransactionInput): Promise<CreateOutcome> {
    await delay(140);
    const fp = fingerprint(input.amount, input.description);
    const matches = this.rows.filter(
      (t) => fingerprint(t.amount, t.description) === fp && daysApart(t.date, input.date) <= 3,
    );
    if (matches.length) {
      return {
        kind: "warning",
        warning: {
          type: "possible_duplicate",
          message: "Có giao dịch tương tự gần đây. Vẫn lưu?",
          matching_transactions: matches.slice(0, 3),
        },
      };
    }
    return { kind: "saved", transaction: await this.create(input) };
  }

  async uploadPdf(filename: string): Promise<ReceiptExtraction> {
    await delay(900);
    void filename;
    return {
      merchant: "WinMart Nguyễn Trãi",
      date: new Date().toISOString().slice(0, 10),
      amount: -347_000,
      category: "Shopping",
      ai_cost_usd: 0.004,
      items: [
        { name: "Sữa tươi TH 1L x2", amount: -68_000 },
        { name: "Trứng gà 10 quả", amount: -42_000 },
        { name: "Rau củ tổng hợp", amount: -55_000 },
        { name: "Thịt heo 500g", amount: -98_000 },
        { name: "Nước giặt", amount: -84_000 },
      ],
    };
  }

  async getBudgets(month?: string): Promise<BudgetsResponse> {
    await delay(120);
    const sum = aggregate(this.rows, month);
    const status: BudgetStatus[] = Object.entries(this.budgets).map(
      ([category, limit]) => {
        const total = sum.by_category[category]?.total ?? 0;
        const spent = total < 0 ? Math.abs(total) : 0;
        const remaining = Math.max(limit - spent, 0);
        return {
          category,
          limit,
          spent,
          remaining,
          percent: limit > 0 ? Math.round((spent / limit) * 1000) / 10 : 0,
          exceeded: spent > limit,
        };
      },
    );
    return {
      budgets: this.budgets,
      status,
      alerts: status.filter((s) => s.exceeded),
    };
  }

  async setBudget(category: string, amount: number): Promise<void> {
    await delay(100);
    this.budgets[category] = amount;
  }

  async enqueueCsv(file: File): Promise<JobStatus> {
    const jobId = `job-${crypto.randomUUID().slice(0, 8)}`;
    const text = /\.csv$/i.test(file.name) ? await file.text() : "";
    const outcome = await this.uploadCsv(text, undefined, file.name);
    const rows = outcome.kind === "ok" ? outcome.result.rows_inserted : 0;
    return { job_id: jobId, status: "COMPLETED", rows_inserted: rows };
  }

  async getJobStatus(jobId: string): Promise<JobStatus> {
    await delay(60);
    return { job_id: jobId, status: "COMPLETED" };
  }

  async getAudit(id: string): Promise<AuditResponse> {
    await delay(80);
    const t = this.rows.find((r) => r.id === id);
    if (!t) return { transaction_id: id, audit: [] };
    const conf = t.confidence ?? "high";
    const source =
      conf === "high" ? "keyword" : conf === "medium" ? "llm" : "fallback";
    return {
      transaction_id: id,
      audit: [
        {
          source,
          category: t.category,
          confidence: conf,
          needs_review: t.needs_review,
          prompt_version: "local",
          model_id: "local",
          ts: new Date().toISOString(),
        },
      ],
    };
  }
}
