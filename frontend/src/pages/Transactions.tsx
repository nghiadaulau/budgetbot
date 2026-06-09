import { useMemo, useState, useRef } from "react";
import { toast } from "sonner";
import {
  Search,
  ListFilter,
  Tag,
  X,
  SlidersHorizontal,
  ArrowUp,
  ArrowDown,
  ChevronsUpDown,
  AlertTriangle,
} from "lucide-react";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { EditableCategoryBadge } from "@/components/CategoryBadge";
import { SourceIcon } from "@/components/transactions/SourceIcon";
import { TransactionDetail } from "@/components/transactions/TransactionDetail";
import { EmptyState } from "@/components/EmptyState";
import { NoResultsIllustration } from "@/components/Illustration";
import { Skeleton } from "@/components/ui/skeleton";
import { useTransactions, useUpdateCategory } from "@/hooks/useApi";
import { useI18n } from "@/context/i18n";
import { useUi } from "@/context/ui";
import {
  CATEGORIES,
  CATEGORY_META,
  type Category,
} from "@/lib/categories";
import type { Transaction, TxnSource } from "@/api/types";
import { formatVnd, formatDateVn, formatMonthLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

const PAGE = 20;

function SortArrow({ active, dir }: { active: boolean; dir: "asc" | "desc" }) {
  if (!active) return <ChevronsUpDown className="size-3.5 opacity-40" />;
  return dir === "asc" ? (
    <ArrowUp className="size-3.5" />
  ) : (
    <ArrowDown className="size-3.5" />
  );
}

export default function Transactions() {
  const { t, lang } = useI18n();
  const { month } = useUi();
  const updateCat = useUpdateCategory();

  const [allMonths, setAllMonths] = useState(false);
  const { data: txns, isLoading } = useTransactions(
    allMonths ? undefined : month,
  );

  const [search, setSearch] = useState("");
  const [cats, setCats] = useState<Category[]>([]);
  const [source, setSource] = useState<"all" | TxnSource>("all");
  const [minAmt, setMinAmt] = useState("");
  const [maxAmt, setMaxAmt] = useState("");
  const [visible, setVisible] = useState(PAGE);
  const [showFilters, setShowFilters] = useState(false);
  const [sort, setSort] = useState<{
    key: "date" | "amount";
    dir: "asc" | "desc";
  }>({ key: "date", dir: "desc" });
  const searchRef = useRef<HTMLInputElement>(null);

  const toggleSort = (key: "date" | "amount") =>
    setSort((s) =>
      s.key === key
        ? { key, dir: s.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "desc" },
    );

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detail, setDetail] = useState<Transaction | null>(null);

  const filtered = useMemo(() => {
    const min = minAmt ? Number(minAmt.replace(/\D/g, "")) : null;
    const max = maxAmt ? Number(maxAmt.replace(/\D/g, "")) : null;
    return (txns ?? []).filter((tx) => {
      if (search && !tx.description.toLowerCase().includes(search.toLowerCase()))
        return false;
      if (cats.length && !cats.includes(tx.category as Category)) return false;
      if (source !== "all" && (tx.source ?? "csv") !== source) return false;
      const abs = Math.abs(tx.amount);
      if (min != null && abs < min) return false;
      if (max != null && abs > max) return false;
      return true;
    });
  }, [txns, search, cats, source, minAmt, maxAmt]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const cmp =
        sort.key === "amount"
          ? a.amount - b.amount
          : a.date.localeCompare(b.date);
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [filtered, sort]);

  const shown = sorted.slice(0, visible);
  const hasFilters =
    search || cats.length || source !== "all" || minAmt || maxAmt;

  const clearFilters = () => {
    setSearch("");
    setCats([]);
    setSource("all");
    setMinAmt("");
    setMaxAmt("");
  };

  const toggleCat = (c: Category) =>
    setCats((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c],
    );

  const toggleSelect = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const allShownSelected =
    shown.length > 0 && shown.every((t) => selected.has(t.id));
  const toggleSelectAll = () =>
    setSelected((prev) => {
      if (allShownSelected) {
        const next = new Set(prev);
        shown.forEach((t) => next.delete(t.id));
        return next;
      }
      return new Set([...prev, ...shown.map((t) => t.id)]);
    });

  const bulkRecategorize = (category: Category) => {
    const ids = [...selected];
    ids.forEach((id) => updateCat.mutate({ id, category }));
    toast.success(t("txn.categoryUpdated"));
    setSelected(new Set());
  };

  const recategorizeOne = (id: string, category: Category) =>
    updateCat.mutate(
      { id, category },
      {
        onSuccess: () => toast.success(t("txn.categoryUpdated")),
        onError: () => toast.error(t("txn.updateFailed")),
      },
    );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-h1">{t("txn.title")}</h2>
        <Button
          variant={allMonths ? "default" : "outline"}
          size="sm"
          onClick={() => setAllMonths((v) => !v)}
        >
          {allMonths ? t("common.all") : formatMonthLabel(month)}
        </Button>
      </div>

      <div className="space-y-2">
       <div className="flex items-center gap-2">
        <div className="relative min-w-[160px] flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            ref={searchRef}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("txn.searchPlaceholder")}
            className="pl-9"
          />
        </div>
        <Button
          variant="outline"
          className="gap-2 sm:hidden"
          aria-expanded={showFilters}
          onClick={() => setShowFilters((v) => !v)}
        >
          <SlidersHorizontal className="size-4" />
          {t("txn.filters")}
        </Button>
       </div>

       <div
        className={cn(
          "flex-wrap items-center gap-2 sm:flex",
          showFilters ? "flex" : "hidden",
        )}
       >
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="gap-2">
              <Tag className="size-4" />
              {cats.length
                ? t("txn.selected", { n: cats.length })
                : t("txn.allCategories")}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
            <DropdownMenuLabel>{t("common.category")}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {CATEGORIES.map((c) => (
              <DropdownMenuCheckboxItem
                key={c}
                checked={cats.includes(c)}
                onCheckedChange={() => toggleCat(c)}
                onSelect={(e) => e.preventDefault()}
              >
                {CATEGORY_META[c][lang]}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <Select
          value={source}
          onValueChange={(v) => setSource(v as "all" | TxnSource)}
        >
          <SelectTrigger className="w-[140px]">
            <ListFilter className="size-4 opacity-60" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("txn.allSources")}</SelectItem>
            <SelectItem value="csv">{t("txn.source.csv")}</SelectItem>
            <SelectItem value="pdf">{t("txn.source.pdf")}</SelectItem>
            <SelectItem value="manual">{t("txn.source.manual")}</SelectItem>
          </SelectContent>
        </Select>

        <div className="flex flex-1 gap-2 sm:flex-none">
          <Input
            value={minAmt}
            onChange={(e) => setMinAmt(e.target.value)}
            inputMode="numeric"
            placeholder={t("txn.min")}
            className="tabular w-full sm:w-24"
          />
          <Input
            value={maxAmt}
            onChange={(e) => setMaxAmt(e.target.value)}
            inputMode="numeric"
            placeholder={t("txn.max")}
            className="tabular w-full sm:w-24"
          />
        </div>

        {hasFilters && (
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("txn.clearFilters")}
            onClick={clearFilters}
          >
            <X className="size-4" />
          </Button>
        )}
       </div>
      </div>

      {selected.size > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-border bg-accent/40 px-4 py-2">
          <span className="text-sm font-medium">
            {t("txn.selected", { n: selected.size })}
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" className="gap-2">
                <Tag className="size-4" />
                {t("txn.recategorize")}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="max-h-72 overflow-y-auto"
            >
              {CATEGORIES.map((c) => (
                <DropdownMenuItem
                  key={c}
                  onSelect={() => bulkRecategorize(c)}
                >
                  {CATEGORY_META[c][lang]}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="divide-y divide-border">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 px-3 py-3">
                  <Skeleton className="size-4 rounded" />
                  <Skeleton className="h-3.5 w-20" />
                  <Skeleton className="h-3.5 flex-1" />
                  <Skeleton className="h-6 w-24 rounded-full" />
                  <Skeleton className="h-3.5 w-24" />
                </div>
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-4">
              <EmptyState
                illustration={<NoResultsIllustration />}
                title={t("txn.noResults")}
                description={t("txn.noResultsDesc")}
                action={
                  hasFilters ? (
                    <Button variant="outline" onClick={clearFilters}>
                      <X className="size-4" />
                      {t("txn.clearFilters")}
                    </Button>
                  ) : undefined
                }
              />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-10">
                    <input
                      type="checkbox"
                      aria-label="Chọn tất cả"
                      checked={allShownSelected}
                      onChange={toggleSelectAll}
                      className="size-4 cursor-pointer accent-[color:var(--primary)]"
                    />
                  </TableHead>
                  <TableHead
                    className="w-28"
                    aria-sort={
                      sort.key === "date"
                        ? sort.dir === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                  >
                    <button
                      type="button"
                      onClick={() => toggleSort("date")}
                      className="-ml-1 inline-flex items-center gap-1 rounded px-1 py-0.5 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {t("common.date")}
                      <SortArrow active={sort.key === "date"} dir={sort.dir} />
                    </button>
                  </TableHead>
                  <TableHead>{t("common.description")}</TableHead>
                  <TableHead className="w-40">{t("common.category")}</TableHead>
                  <TableHead
                    className="w-32 text-right"
                    aria-sort={
                      sort.key === "amount"
                        ? sort.dir === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                  >
                    <button
                      type="button"
                      onClick={() => toggleSort("amount")}
                      className="-mr-1 ml-auto inline-flex items-center gap-1 rounded px-1 py-0.5 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {t("common.amount")}
                      <SortArrow active={sort.key === "amount"} dir={sort.dir} />
                    </button>
                  </TableHead>
                  <TableHead className="w-14 text-center">
                    {t("common.source")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {shown.map((tx) => (
                  <TableRow
                    key={tx.id}
                    data-state={selected.has(tx.id) ? "selected" : undefined}
                    className="cursor-pointer"
                    onClick={() => setDetail(tx)}
                  >
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        aria-label={`Chọn ${tx.description}`}
                        checked={selected.has(tx.id)}
                        onChange={() => toggleSelect(tx.id)}
                        className="size-4 cursor-pointer accent-[color:var(--primary)]"
                      />
                    </TableCell>
                    <TableCell className="tabular whitespace-nowrap text-sm text-muted-foreground">
                      {formatDateVn(tx.date)}
                    </TableCell>
                    <TableCell className="max-w-[1px]">
                      <span className="block truncate font-medium">
                        {tx.description}
                      </span>
                      {tx.needs_review && (
                        <span
                          title={t("txn.needsReviewHint")}
                          className="mt-1 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium text-[color:var(--warning)] bg-[color:var(--warning)]/10"
                        >
                          <AlertTriangle className="size-3" />
                          {t("txn.needsReview")}
                        </span>
                      )}
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <EditableCategoryBadge
                        category={tx.category as Category}
                        size="sm"
                        onChange={(c) => recategorizeOne(tx.id, c)}
                      />
                    </TableCell>
                    <TableCell
                      className={`tabular whitespace-nowrap text-right font-semibold ${
                        tx.amount < 0
                          ? "text-foreground"
                          : "text-[color:var(--positive)]"
                      }`}
                    >
                      {tx.amount < 0 ? "" : "+"}
                      {formatVnd(tx.amount)}
                    </TableCell>
                    <TableCell className="text-center">
                      <span className="inline-flex justify-center">
                        <SourceIcon source={tx.source} />
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {filtered.length > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <Badge className="border-border bg-secondary text-secondary-foreground">
            {t("txn.count", { n: filtered.length })}
          </Badge>
          {visible < filtered.length && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setVisible((v) => v + PAGE)}
            >
              {t("common.viewAll")} ({filtered.length - visible})
            </Button>
          )}
        </div>
      )}

      <TransactionDetail
        txn={detail}
        open={!!detail}
        onClose={() => setDetail(null)}
      />
    </div>
  );
}
