import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  Cell,
} from "recharts";
import { formatVndCompact } from "@/lib/format";
import { CurrencyTooltip } from "./ChartTooltip";
import { useReducedMotion } from "@/hooks/useMediaQuery";

interface Datum {
  month: string;
  label: string;
  value: number;
}

export function MonthlyBar({
  data,
  activeMonth,
}: {
  data: Datum[];
  activeMonth: string;
}) {
  const reduced = useReducedMotion();
  return (
    <div className="h-[240px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
          <XAxis
            dataKey="label"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            interval={0}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            width={46}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            tickFormatter={(v) => formatVndCompact(Number(v))}
          />
          <Tooltip
            cursor={{ fill: "var(--muted)", opacity: 0.5 }}
            content={<CurrencyTooltip />}
          />
          <Bar
            dataKey="value"
            radius={[6, 6, 0, 0]}
            maxBarSize={48}
            isAnimationActive={!reduced}
            animationDuration={300}
            animationEasing="ease-out"
          >
            {data.map((d) => (
              <Cell
                key={d.month}
                fill={
                  d.month === activeMonth ? "var(--primary)" : "var(--chart-1)"
                }
                fillOpacity={d.month === activeMonth ? 1 : 0.35}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
