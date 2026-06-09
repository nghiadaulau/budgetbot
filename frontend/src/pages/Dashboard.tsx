import { Link } from "react-router-dom";
import { FileSpreadsheet, FileText, Plus, ArrowRight } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/StatCard";
import { EmptyWalletIllustration } from "@/components/Illustration";
import { CategoryDonut } from "@/components/charts/CategoryDonut";
import { MonthlyBar } from "@/components/charts/MonthlyBar";
import { CategoryBadge } from "@/components/CategoryBadge";
import { SourceIcon } from "@/components/transactions/SourceIcon";
import { useAllTransactions } from "@/hooks/useApi";
import { useI18n } from "@/context/i18n";
import { useUi } from "@/context/ui";
import {
  buildSummary,
  monthStats,
  monthlyExpenseTotals,
} from "@/lib/aggregate";
import {
  formatVnd,
  formatRelative,
  formatDateLong,
  lastNMonths,
  shiftMonth,
  percentDelta,
} from "@/lib/format";
import type { Category } from "@/lib/categories";

function QuickAction({
  icon,
  title,
  desc,
  onClick,
  to,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  onClick?: () => void;
  to?: string;
}) {
  const inner = (
    <Card className="group flex h-full cursor-pointer items-center gap-3 p-4 transition-[transform,background-color,border-color] duration-150 ease-out hover:border-ring hover:bg-secondary/50 active:scale-[.99]">
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-secondary text-foreground transition-colors group-hover:bg-card">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block font-semibold">{title}</span>
        <span className="block text-xs text-muted-foreground">{desc}</span>
      </span>
      <ArrowRight className="ml-auto size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
    </Card>
  );
  if (to) return <Link to={to}>{inner}</Link>;
  return (
    <button type="button" onClick={onClick} className="text-left">
      {inner}
    </button>
  );
}

export default function Dashboard() {
  const { t, lang } = useI18n();
  const { month, setQuickAddOpen } = useUi();
  const { data: txns, isLoading } = useAllTransactions();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  const all = txns ?? [];

  if (all.length === 0) {
    return (
      <div className="space-y-6">
        <h2 className="text-h1">{t("dashboard.welcome")}</h2>
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border bg-card/50 px-6 py-10 text-center">
          <EmptyWalletIllustration />
          <h3 className="text-h2 mt-2">{t("dashboard.empty.title")}</h3>
          <p className="text-body max-w-md text-muted-foreground">
            {t("dashboard.empty.desc")}
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <QuickAction
            to="/upload"
            icon={<FileSpreadsheet className="size-5" />}
            title={t("action.uploadCsv")}
            desc={t("action.uploadCsv.desc")}
          />
          <QuickAction
            to="/receipt"
            icon={<FileText className="size-5" />}
            title={t("action.addReceipt")}
            desc={t("action.addReceipt.desc")}
          />
          <QuickAction
            onClick={() => setQuickAddOpen(true)}
            icon={<Plus className="size-5" />}
            title={t("action.quickAdd")}
            desc={t("action.quickAdd.desc")}
          />
        </div>
      </div>
    );
  }

  const stats = monthStats(all, month);
  const prev = monthStats(all, shiftMonth(month, -1));
  const summary = buildSummary(all, month);
  const sixMonths = monthlyExpenseTotals(all, lastNMonths(month, 6));

  const recent = all
    .filter((tx) => tx.date.startsWith(month))
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, 10);

  return (
    <div className="space-y-6">
      <h2 className="text-h1">
        {t("dashboard.welcome")}
      </h2>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label={t("dashboard.spentThisMonth")}
          amount={stats.spent}
          tone="expense"
          delta={percentDelta(stats.spent, prev.spent)}
        />
        <StatCard
          label={t("dashboard.income")}
          amount={stats.income}
          tone="income"
          delta={percentDelta(stats.income, prev.income)}
        />
        <StatCard
          label={t("dashboard.net")}
          amount={stats.net}
          tone="net"
          delta={percentDelta(stats.net, prev.net)}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("dashboard.spendingByCategory")}</CardTitle>
          </CardHeader>
          <CardContent>
            <CategoryDonut summary={summary} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("dashboard.last6Months")}</CardTitle>
          </CardHeader>
          <CardContent>
            <MonthlyBar data={sixMonths} activeMonth={month} />
          </CardContent>
        </Card>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-muted-foreground">
          {t("dashboard.quickActions")}
        </h3>
        <div className="grid gap-3 sm:grid-cols-3">
          <QuickAction
            to="/upload"
            icon={<FileSpreadsheet className="size-5" />}
            title={t("action.uploadCsv")}
            desc={t("action.uploadCsv.desc")}
          />
          <QuickAction
            to="/receipt"
            icon={<FileText className="size-5" />}
            title={t("action.addReceipt")}
            desc={t("action.addReceipt.desc")}
          />
          <QuickAction
            onClick={() => setQuickAddOpen(true)}
            icon={<Plus className="size-5" />}
            title={t("action.quickAdd")}
            desc={t("action.quickAdd.desc")}
          />
        </div>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>{t("dashboard.recentTransactions")}</CardTitle>
          <Button asChild variant="ghost" size="sm" className="gap-1">
            <Link to="/transactions">
              {t("common.viewAll")}
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        </CardHeader>
        <CardContent>
          {recent.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {t("dashboard.noRecent")}
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {recent.map((tx) => (
                <li
                  key={tx.id}
                  className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {tx.description}
                    </p>
                    <p className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="tabular" title={formatDateLong(tx.date, lang)}>
                        {formatRelative(tx.date, lang)}
                      </span>
                      <SourceIcon source={tx.source} />
                    </p>
                  </div>
                  <CategoryBadge
                    category={tx.category as Category}
                    size="sm"
                    className="hidden sm:inline-flex"
                  />
                  <span
                    className={`tabular w-28 shrink-0 text-right text-sm font-semibold ${
                      tx.amount < 0
                        ? "text-foreground"
                        : "text-[color:var(--positive)]"
                    }`}
                  >
                    {tx.amount < 0 ? "" : "+"}
                    {formatVnd(tx.amount)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
