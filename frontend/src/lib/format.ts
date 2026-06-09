/**
 * Formatting helpers — VND currency and Vietnamese dates.
 * Amounts are ALWAYS rendered through these; never show raw "1250000".
 */

const vndFormatter = new Intl.NumberFormat("vi-VN", {
  style: "currency",
  currency: "VND",
  maximumFractionDigits: 0,
});

const numberFormatter = new Intl.NumberFormat("vi-VN", {
  maximumFractionDigits: 0,
});

/** "1.250.000 ₫" — dot thousand separator, ₫ suffix (vi-VN locale). */
export function formatVnd(amount: number): string {
  return vndFormatter.format(Math.round(amount));
}

/** Absolute amount with an explicit sign: "+18.500.000 ₫" / "−65.000 ₫". */
export function formatSignedVnd(amount: number): string {
  const sign = amount > 0 ? "+" : amount < 0 ? "−" : "";
  return `${sign}${vndFormatter.format(Math.abs(Math.round(amount)))}`;
}

/** Plain grouped number, no currency: "1.250.000". Used in amount inputs. */
export function formatThousands(value: number | string): string {
  const n = typeof value === "string" ? Number(value.replace(/\D/g, "")) : value;
  if (!Number.isFinite(n)) return "";
  return numberFormatter.format(n);
}

/** VN percentage with comma decimal: "12,5%" / "38%". */
export function formatPercentVn(value: number, decimals = 1): string {
  const s = new Intl.NumberFormat("vi-VN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  }).format(value);
  return `${s}%`;
}

/** Compact VND for chart axes: "1,2 Tr", "450 N". */
export function formatVndCompact(amount: number): string {
  const abs = Math.abs(amount);
  if (abs >= 1_000_000_000)
    return `${(amount / 1_000_000_000).toFixed(1).replace(".", ",")} Tỷ`;
  if (abs >= 1_000_000)
    return `${(amount / 1_000_000).toFixed(1).replace(".", ",")} Tr`;
  if (abs >= 1_000) return `${Math.round(amount / 1_000)} N`;
  return String(Math.round(amount));
}

const VN_MONTHS = [
  "Th1", "Th2", "Th3", "Th4", "Th5", "Th6",
  "Th7", "Th8", "Th9", "Th10", "Th11", "Th12",
];

function toDate(input: string | Date): Date {
  return input instanceof Date ? input : new Date(input);
}

/** "15 Th6 2026" — Vietnamese short month. */
export function formatDateVn(input: string | Date): string {
  const d = toDate(input);
  if (Number.isNaN(d.getTime())) return String(input);
  return `${d.getDate()} ${VN_MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

const EN_MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** "15 tháng 6, 2026" (vi) / "15 Jun 2026" (en) — full date for detail views. */
export function formatDateLong(input: string | Date, lang: "vi" | "en" = "vi"): string {
  const d = toDate(input);
  if (Number.isNaN(d.getTime())) return String(input);
  if (lang === "vi") {
    return `${d.getDate()} tháng ${d.getMonth() + 1}, ${d.getFullYear()}`;
  }
  return `${d.getDate()} ${EN_MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

/** Relative time for recent lists: "Hôm nay", "2 ngày trước", "3 tuần trước". */
export function formatRelative(input: string | Date, lang: "vi" | "en" = "vi"): string {
  const d = toDate(input);
  if (Number.isNaN(d.getTime())) return String(input);
  const today = new Date();
  const startOfDay = (x: Date) =>
    new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((startOfDay(today) - startOfDay(d)) / 86_400_000);

  if (days < 0) return formatDateVn(d);
  const vi = lang === "vi";
  if (days === 0) return vi ? "Hôm nay" : "Today";
  if (days === 1) return vi ? "Hôm qua" : "Yesterday";
  if (days < 7) return vi ? `${days} ngày trước` : `${days} days ago`;
  if (days < 30) {
    const w = Math.floor(days / 7);
    return vi ? `${w} tuần trước` : `${w} week${w > 1 ? "s" : ""} ago`;
  }
  return formatDateVn(d);
}

/** "15/06/2026" — numeric date. */
export function formatDateNumeric(input: string | Date): string {
  const d = toDate(input);
  if (Number.isNaN(d.getTime())) return String(input);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getFullYear()}`;
}

/** "Th6 2026" — month label for the month picker / chart titles. */
export function formatMonthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  if (!y || !m) return month;
  return `${VN_MONTHS[m - 1]} ${y}`;
}

/** Today as "YYYY-MM-DD" in local time. */
export function todayIso(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

/** Current month as "YYYY-MM". */
export function currentMonth(): string {
  return todayIso().slice(0, 7);
}

/** Shift a "YYYY-MM" string by n months (negative = past). */
export function shiftMonth(month: string, n: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + n, 1);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${d.getFullYear()}-${mm}`;
}

/** Last `count` months ending at `month` (inclusive), oldest first. */
export function lastNMonths(month: string, count: number): string[] {
  return Array.from({ length: count }, (_, i) =>
    shiftMonth(month, -(count - 1 - i)),
  );
}

/** Percentage delta vs a previous value, rounded. Null when no baseline. */
export function percentDelta(current: number, previous: number): number | null {
  if (!previous) return null;
  return Math.round(((current - previous) / Math.abs(previous)) * 100);
}
