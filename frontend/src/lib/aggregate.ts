import type { Transaction, Summary } from "@/api/types";
import { formatMonthLabel } from "@/lib/format";

/** Aggregate a transaction list into the Summary shape (client-side). */
export function buildSummary(rows: Transaction[], month?: string): Summary {
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

export interface MonthStats {
  spent: number;
  income: number;
  net: number;
}

export function monthStats(rows: Transaction[], month: string): MonthStats {
  let spent = 0;
  let income = 0;
  for (const t of rows) {
    if (!t.date.startsWith(month)) continue;
    if (t.amount < 0) spent += Math.abs(t.amount);
    else income += t.amount;
  }
  return { spent, income, net: income - spent };
}

/** Expense totals (positive magnitude) per month, for the 6-month bar chart. */
export function monthlyExpenseTotals(rows: Transaction[], months: string[]) {
  return months.map((m) => ({
    month: m,
    label: formatMonthLabel(m).split(" ")[0],
    value: monthStats(rows, m).spent,
  }));
}

/** Top merchants by total spend (groups identical descriptions). */
export function topMerchants(rows: Transaction[], month?: string, limit = 6) {
  const scoped = month ? rows.filter((t) => t.date.startsWith(month)) : rows;
  const map = new Map<string, { total: number; count: number }>();
  for (const t of scoped) {
    if (t.amount >= 0) continue;
    const cur = map.get(t.description) ?? { total: 0, count: 0 };
    cur.total += Math.abs(t.amount);
    cur.count += 1;
    map.set(t.description, cur);
  }
  return [...map.entries()]
    .map(([name, v]) => ({ name, ...v }))
    .sort((a, b) => b.total - a.total)
    .slice(0, limit);
}
