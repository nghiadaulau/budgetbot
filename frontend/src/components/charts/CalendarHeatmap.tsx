import type { Summary } from "@/api/types";
import { useI18n } from "@/context/i18n";
import { formatVnd, formatDateVn } from "@/lib/format";

const WEEKDAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];

/** Calendar heatmap of daily spend for a "YYYY-MM" month. */
export function CalendarHeatmap({
  month,
  summary,
}: {
  month: string;
  summary: Summary;
}) {
  const { t } = useI18n();
  const [y, m] = month.split("-").map(Number);
  const daysInMonth = new Date(y, m, 0).getDate();
  const firstWeekday = (new Date(y, m - 1, 1).getDay() + 6) % 7;

  const byDay = new Map<number, number>();
  for (const d of summary.daily_trends) {
    const day = Number(d.date.slice(8, 10));
    if (day) byDay.set(day, d.amount);
  }
  const max = Math.max(1, ...byDay.values());

  const intensity = (amount: number) => {
    if (!amount) return 0;
    const r = amount / max;
    if (r > 0.66) return 3;
    if (r > 0.33) return 2;
    return 1;
  };
  const bg = ["var(--muted)", "var(--chart-1)", "var(--chart-1)", "var(--chart-1)"];
  const op = [1, 0.35, 0.65, 1];

  const cells: (number | null)[] = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  return (
    <div>
      <div className="grid grid-cols-7 gap-1.5">
        {WEEKDAYS.map((w) => (
          <div
            key={w}
            className="pb-1 text-center text-[11px] font-medium text-muted-foreground"
          >
            {w}
          </div>
        ))}
        {cells.map((day, i) => {
          if (day == null) return <div key={`b${i}`} />;
          const amount = byDay.get(day) ?? 0;
          const lvl = intensity(amount);
          const date = `${month}-${String(day).padStart(2, "0")}`;
          return (
            <div
              key={day}
              title={`${formatDateVn(date)} · ${formatVnd(amount)}`}
              className="flex aspect-square items-center justify-center rounded-md text-[11px] tabular"
              style={{
                backgroundColor: bg[lvl],
                opacity: op[lvl],
                color: lvl >= 2 ? "#fff" : "var(--muted-foreground)",
              }}
            >
              {day}
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex items-center justify-end gap-1.5 text-[11px] text-muted-foreground">
        <span>{t("insights.less")}</span>
        {op.map((o, i) => (
          <span
            key={i}
            className="size-3 rounded-sm"
            style={{ backgroundColor: bg[i], opacity: o }}
          />
        ))}
        <span>{t("insights.more")}</span>
      </div>
    </div>
  );
}
