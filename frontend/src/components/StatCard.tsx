import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import { Card } from "@/components/ui/card";
import { formatVnd, formatPercentVn } from "@/lib/format";
import { useI18n } from "@/context/i18n";
import { cn } from "@/lib/utils";

type Tone = "expense" | "income" | "net";

interface Props {
  label: string;
  amount: number;
  tone: Tone;
  /** Percent change vs last month; null hides the comparison. */
  delta: number | null;
}

export function StatCard({ label, amount, tone, delta }: Props) {
  const { t } = useI18n();

  const amountColor =
    tone === "income"
      ? "text-[color:var(--positive)]"
      : tone === "expense"
        ? "text-foreground"
        : amount >= 0
          ? "text-[color:var(--positive)]"
          : "text-[color:var(--negative)]";

  const goodWhenUp = tone !== "expense";
  const up = delta != null && delta > 0;
  const flat = delta === 0 || delta === null;
  const deltaGood = flat ? false : up === goodWhenUp;
  const DeltaIcon = flat ? Minus : up ? ArrowUpRight : ArrowDownRight;

  const displayAmount =
    tone === "net" ? amount : tone === "income" ? amount : -amount;

  return (
    <Card className="p-6">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className={cn("tabular mt-1.5 text-2xl font-semibold", amountColor)}>
        {tone === "net" && amount > 0 ? "+" : ""}
        {formatVnd(displayAmount)}
      </p>
      {delta != null ? (
        <p
          className={cn(
            "mt-2 flex items-center gap-1 text-xs font-medium",
            flat
              ? "text-muted-foreground"
              : deltaGood
                ? "text-[color:var(--positive)]"
                : "text-[color:var(--negative)]",
          )}
        >
          <DeltaIcon className="size-3.5" />
          <span className="tabular">{formatPercentVn(Math.abs(delta), 0)}</span>{" "}
          {t("dashboard.vsLastMonth")}
        </p>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">
          {t("dashboard.vsLastMonth")} —
        </p>
      )}
    </Card>
  );
}
