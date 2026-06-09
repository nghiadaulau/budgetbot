import { useState } from "react";
import { TrendingDown, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { DailyTrend } from "@/components/charts/DailyTrend";
import { CalendarHeatmap } from "@/components/charts/CalendarHeatmap";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { useTransactions, useBudgets, useSetBudget } from "@/hooks/useApi";
import { useI18n } from "@/context/i18n";
import { useUi } from "@/context/ui";
import { buildSummary, topMerchants } from "@/lib/aggregate";
import { CATEGORIES, categoryLabel, type Category } from "@/lib/categories";
import { formatVnd, formatThousands } from "@/lib/format";

/** Categories worth budgeting — spending only (excludes income & transfers). */
const BUDGET_CATEGORIES = CATEGORIES.filter(
  (c) => c !== "Salary" && c !== "Transfer",
);

/** Inline form to set/update a monthly cap — mirrors the chatbot's set_budget tool. */
function SetBudgetForm() {
  const { t, lang } = useI18n();
  const setBudget = useSetBudget();
  const [category, setCategory] = useState<Category>("Food");
  const [amount, setAmount] = useState("");

  const submit = () => {
    const value = Number(amount.replace(/[^\d]/g, ""));
    if (!value || value <= 0) {
      toast.error(t("insights.budgetInvalid"));
      return;
    }
    setBudget.mutate(
      { category, amount: value },
      {
        onSuccess: () => {
          toast.success(t("insights.budgetSaved"));
          setAmount("");
        },
        onError: () => toast.error(t("insights.budgetInvalid")),
      },
    );
  };

  return (
    <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-center">
      <Select value={category} onValueChange={(v) => setCategory(v as Category)}>
        <SelectTrigger className="sm:w-44">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {BUDGET_CATEGORIES.map((c) => (
            <SelectItem key={c} value={c}>
              {categoryLabel(c, lang)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Input
        inputMode="numeric"
        value={amount}
        placeholder={t("insights.budgetAmount")}
        onChange={(e) => setAmount(formatThousands(e.target.value))}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        className="flex-1"
      />
      <Button onClick={submit} disabled={setBudget.isPending}>
        {t("common.save")}
      </Button>
    </div>
  );
}

export default function Insights() {
  const { t, lang } = useI18n();
  const { month } = useUi();
  const { data: txns, isLoading } = useTransactions(month);
  const { data: budgets } = useBudgets(month);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-64 w-full" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }

  const rows = txns ?? [];
  const summary = buildSummary(rows, month);
  const merchants = topMerchants(rows, month);
  const status = budgets?.status ?? [];

  return (
    <div className="space-y-6">
      <h2 className="text-h1">{t("insights.title")}</h2>

      <Card>
        <CardHeader>
          <CardTitle>{t("insights.heatmapDesc")}</CardTitle>
        </CardHeader>
        <CardContent>
          <DailyTrend summary={summary} />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("insights.heatmap")}</CardTitle>
            <CardDescription>{t("insights.heatmapDesc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <CalendarHeatmap month={month} summary={summary} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("insights.topMerchants")}</CardTitle>
          </CardHeader>
          <CardContent>
            {merchants.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                —
              </p>
            ) : (
              <ul className="space-y-1">
                {merchants.map((mch, i) => (
                  <li
                    key={mch.name}
                    className="flex items-center gap-3 py-1.5"
                  >
                    <span className="tabular w-5 text-sm font-semibold text-muted-foreground">
                      {i + 1}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">
                      {mch.name}
                    </span>
                    <span className="tabular text-sm font-semibold">
                      {formatVnd(mch.total)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("insights.budgetVsActual")}</CardTitle>
        </CardHeader>
        <CardContent>
          <SetBudgetForm />
          {status.length === 0 ? (
            <EmptyState
              title={t("insights.budgetVsActual")}
              description={t("insights.noBudgets")}
              icon={<TrendingDown className="size-8" />}
            />
          ) : (
            <ul className="space-y-4">
              {status.map((b) => (
                <li key={b.category} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <CategoryBadge
                      category={b.category as Category}
                      size="sm"
                    />
                    <span className="tabular text-sm">
                      <span
                        className={
                          b.exceeded
                            ? "font-semibold text-[color:var(--negative)]"
                            : "font-semibold"
                        }
                      >
                        {formatVnd(b.spent)}
                      </span>
                      <span className="text-muted-foreground">
                        {" / "}
                        {formatVnd(b.limit)}
                      </span>
                    </span>
                  </div>
                  <Progress
                    value={b.percent}
                    indicatorClassName={
                      b.exceeded
                        ? "bg-[color:var(--negative)]"
                        : "bg-[color:var(--positive)]"
                    }
                  />
                  <div className="flex items-center justify-between text-xs">
                    {b.exceeded ? (
                      <span className="flex items-center gap-1 font-medium text-[color:var(--negative)]">
                        <AlertTriangle className="size-3.5" />
                        {t("insights.overBudget")}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">
                        {categoryLabel(b.category, lang)}
                      </span>
                    )}
                    <span className="tabular text-muted-foreground">
                      {t("insights.remaining")}: {formatVnd(b.remaining)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
