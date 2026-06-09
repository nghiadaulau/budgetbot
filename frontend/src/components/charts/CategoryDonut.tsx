import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import type { Summary } from "@/api/types";
import {
  categoryColor,
  categoryLabel,
  type Category,
} from "@/lib/categories";
import { useI18n } from "@/context/i18n";
import { formatVnd, formatVndCompact, formatPercentVn } from "@/lib/format";
import { CurrencyTooltip } from "./ChartTooltip";
import { ChartEmpty } from "@/components/EmptyState";
import { useReducedMotion } from "@/hooks/useMediaQuery";

export function CategoryDonut({ summary }: { summary: Summary }) {
  const { t, lang } = useI18n();
  const reduced = useReducedMotion();

  const data = Object.entries(summary.by_category)
    .filter(([, v]) => v.total < 0)
    .map(([cat, v]) => ({
      name: categoryLabel(cat, lang),
      label: categoryLabel(cat, lang),
      value: Math.abs(v.total),
      color: categoryColor(cat),
      category: cat as Category,
    }))
    .sort((a, b) => b.value - a.value);

  const total = data.reduce((s, d) => s + d.value, 0);

  if (!data.length) {
    return <ChartEmpty message={t("chart.noData")} />;
  }

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row">
      <div className="relative h-[200px] w-[200px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={62}
              outerRadius={92}
              paddingAngle={2}
              strokeWidth={0}
              isAnimationActive={!reduced}
              animationDuration={300}
              animationEasing="ease-out"
            >
              {data.map((d) => (
                <Cell key={d.category} fill={d.color} />
              ))}
            </Pie>
            <Tooltip content={<CurrencyTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xs text-muted-foreground">Tổng</span>
          <span
            className="tabular text-lg font-semibold"
            title={formatVnd(-total)}
          >
            {formatVndCompact(-total)}
          </span>
        </div>
      </div>

      <ul className="grid w-full grid-cols-1 gap-1.5 sm:grid-cols-1">
        {data.slice(0, 6).map((d) => (
          <li
            key={d.category}
            className="flex items-center justify-between gap-2 text-sm"
          >
            <span className="flex min-w-0 items-center gap-2">
              <span
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: d.color }}
              />
              <span className="truncate">{d.name}</span>
            </span>
            <span className="flex items-center gap-2">
              <span className="tabular text-xs text-muted-foreground">
                {formatPercentVn((d.value / total) * 100, 0)}
              </span>
              <span className="tabular font-medium">{formatVnd(d.value)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
