import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { Summary } from "@/api/types";
import { formatVndCompact, formatDateVn } from "@/lib/format";
import { CurrencyTooltip } from "./ChartTooltip";
import { ChartEmpty } from "@/components/EmptyState";
import { useI18n } from "@/context/i18n";
import { useReducedMotion } from "@/hooks/useMediaQuery";

export function DailyTrend({ summary }: { summary: Summary }) {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const data = summary.daily_trends.map((d) => ({
    label: formatDateVn(d.date).split(" ").slice(0, 2).join(" "),
    value: d.amount,
  }));

  if (data.length < 2) {
    return <ChartEmpty message={t("chart.noData")} />;
  }

  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
          <defs>
            <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="label"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            minTickGap={24}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            width={46}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            tickFormatter={(v) => formatVndCompact(Number(v))}
          />
          <Tooltip content={<CurrencyTooltip />} />
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--chart-1)"
            strokeWidth={2}
            fill="url(#trendFill)"
            isAnimationActive={!reduced}
            animationDuration={300}
            animationEasing="ease-out"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
