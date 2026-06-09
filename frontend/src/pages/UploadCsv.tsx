import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ArrowRight,
  Files,
  ChevronDown,
  ChevronRight,
  CopyMinus,
} from "lucide-react";
import { toast } from "sonner";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Dropzone } from "@/components/Dropzone";
import { PageHeader } from "@/components/layout/PageHeader";
import { EditableCategoryBadge } from "@/components/CategoryBadge";
import { useI18n } from "@/context/i18n";
import { useUpdateCategory, useInvalidateData } from "@/hooks/useApi";
import { api, shouldUseAsync } from "@/api/client";
import type {
  Transaction,
  UploadResult,
  UploadForce,
  DuplicateFileInfo,
} from "@/api/types";
import type { Category } from "@/lib/categories";
import { formatVnd, formatDateVn } from "@/lib/format";

type Phase = "idle" | "processing" | "duplicate" | "done" | "error";
type Stage = "reading" | "parsing" | "categorizing" | "done";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function countDataRows(text: string): number {
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  return lines.filter((l, i) => {
    if (i === 0 && /date/i.test(l) && /amount/i.test(l)) return false;
    return l.split(",").length >= 3;
  }).length;
}

export default function UploadCsv() {
  const { t } = useI18n();
  const updateCat = useUpdateCategory();
  const invalidateData = useInvalidateData();

  const [phase, setPhase] = useState<Phase>("idle");
  const [stage, setStage] = useState<Stage>("reading");
  const [progress, setProgress] = useState(0);
  const [count, setCount] = useState(0);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [rows, setRows] = useState<Transaction[]>([]);
  const [dup, setDup] = useState<{ info: DuplicateFileInfo; message: string } | null>(null);
  const [showDups, setShowDups] = useState(false);
  const [asyncMode, setAsyncMode] = useState(false);
  const lastFile = useRef<File | null>(null);

  const reset = () => {
    setPhase("idle");
    setProgress(0);
    setResult(null);
    setRows([]);
    setDup(null);
    setShowDups(false);
    setAsyncMode(false);
    lastFile.current = null;
  };

  async function runAsync(file: File) {
    lastFile.current = file;
    setAsyncMode(true);
    setPhase("processing");
    setStage("categorizing");
    setProgress(25);
    try {
      let job = await api.enqueueCsv(file);
      let guard = 0;
      while ((job.status === "QUEUED" || job.status === "PROCESSING") && guard < 60) {
        setProgress((p) => Math.min(90, p + 8));
        await sleep(1500);
        job = await api.getJobStatus(job.job_id);
        guard += 1;
      }
      if (job.status !== "COMPLETED") {
        setPhase("error");
        return;
      }
      const n = job.rows_inserted ?? 0;
      setProgress(100);
      setStage("done");
      setCount(n);
      setRows([]);
      setResult({
        rows_parsed: n,
        rows_inserted: n,
        transactions: [],
        summary: { total_rows: n, new_saved: n, duplicates_skipped: 0, errors: 0 },
      } as UploadResult);
      invalidateData();
      setPhase("done");
    } catch {
      setPhase("error");
    }
  }

  async function run(file: File, force?: UploadForce) {
    lastFile.current = file;
    const isCsv = /\.csv$/i.test(file.name);
    const isExcel = /\.(xlsx|xls)$/i.test(file.name);
    if (!isCsv && !isExcel) {
      setPhase("error");
      return;
    }
    if (shouldUseAsync(file) && !force) {
      await runAsync(file);
      return;
    }
    setPhase("processing");
    setStage("reading");
    setProgress(12);
    try {
      if (isCsv) {
        const n = countDataRows(await file.text());
        if (n === 0) {
          setPhase("error");
          return;
        }
        setCount(n);
      } else {
        setCount(0);
      }
      setStage("parsing");
      setProgress(40);
      await sleep(550);
      setStage("categorizing");
      setProgress(78);
      const outcome = await api.uploadCsv(file, force);
      if (outcome.kind === "duplicate") {
        setDup({ info: outcome.info, message: outcome.message });
        setPhase("duplicate");
        return;
      }
      setProgress(100);
      setStage("done");
      setResult(outcome.result);
      setRows(outcome.result.transactions);
      setCount(outcome.result.rows_inserted);
      invalidateData();
      setPhase("done");
    } catch {
      setPhase("error");
    }
  }

  function onRecategorize(id: string, category: Category) {
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, category } : r)));
    updateCat.mutate(
      { id, category },
      {
        onSuccess: () => toast.success(t("txn.categoryUpdated")),
        onError: () => toast.error(t("txn.updateFailed")),
      },
    );
  }

  const stageLabel =
    stage === "reading"
      ? t("csv.reading")
      : stage === "parsing"
        ? count > 0
          ? t("csv.parsing", { n: count })
          : t("csv.reading")
        : stage === "categorizing"
          ? count > 0
            ? t("csv.categorizing", { n: count })
            : t("csv.categorizingGeneric")
          : t("csv.done");

  const costText =
    result?.ai_cost_usd != null ? `$${result.ai_cost_usd.toFixed(3)}` : "$0.005";
  const dupCount = result?.summary?.duplicates_skipped ?? 0;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title={t("csv.title")} subtitle={t("csv.subtitle")} />

      {phase === "idle" && (
        <Dropzone
          accept=".csv,text/csv,.xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
          onFile={(f) => run(f)}
          title={t("csv.dropHere")}
          hint={t("csv.supports")}
          icon={<FileSpreadsheet className="size-7" />}
        />
      )}

      {phase === "error" && (
        <Card className="border-[color:var(--negative)]/40">
          <CardContent className="flex items-start gap-3 p-6">
            <AlertTriangle className="mt-0.5 size-5 shrink-0 text-[color:var(--negative)]" />
            <div className="flex-1">
              <p className="font-medium">{t("csv.errorFormat")}</p>
              <Button onClick={reset} variant="outline" size="sm" className="mt-3">
                {t("common.retry")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {phase === "processing" && (
        <Card>
          <CardContent className="space-y-4 p-6">
            <div className="flex items-center gap-3">
              {stage === "done" ? (
                <CheckCircle2 className="size-5 text-[color:var(--positive)]" />
              ) : (
                <Loader2 className="size-5 animate-spin text-primary" />
              )}
              <span className="font-medium">
                {asyncMode ? t("csv.asyncProcessing") : stageLabel}
              </span>
            </div>
            <Progress value={progress} />
            {!asyncMode && (
              <p className="text-xs text-muted-foreground">
                {t("csv.costHint", { cost: "$0.005" })}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {phase === "duplicate" && dup && (
        <Card className="border-[color:var(--warning)]/50">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Files className="size-5 text-[color:var(--warning)]" />
              <CardTitle>{t("dup.fileTitle")}</CardTitle>
            </div>
            <CardDescription>{dup.message}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <ChoiceRow
              label={t("dup.skip")}
              hint={t("dup.skipHint")}
              onClick={reset}
            />
            <ChoiceRow
              label={t("dup.append")}
              hint={t("dup.appendHint")}
              primary
              onClick={() => lastFile.current && run(lastFile.current, "append")}
            />
            <ChoiceRow
              label={t("dup.replace")}
              hint={t("dup.replaceHint")}
              danger
              onClick={() => lastFile.current && run(lastFile.current, "replace")}
            />
          </CardContent>
        </Card>
      )}

      {phase === "done" && result && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="size-5 text-[color:var(--positive)]" />
              <CardTitle>
                {t("csv.resultsTitle", { n: result.rows_inserted })}
              </CardTitle>
            </div>
            <CardDescription>
              {asyncMode
                ? t("csv.asyncDone", { n: count })
                : t("csv.costHint", { cost: costText })}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {result.ai_warning && (
              <div className="flex items-start gap-2 rounded-lg border border-[color:var(--warning)]/40 bg-[color:var(--warning)]/10 p-3 text-sm">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-[color:var(--warning)]" />
                <span>{result.ai_warning.message}</span>
              </div>
            )}
            {dupCount > 0 && (
              <div className="rounded-lg border border-[color:var(--warning)]/40 bg-[color:var(--warning)]/10 p-3">
                <div className="flex items-center gap-2 text-sm">
                  <CopyMinus className="size-4 text-[color:var(--warning)]" />
                  <span className="font-medium">
                    {t("dup.summary", {
                      saved: result.summary?.new_saved ?? result.rows_inserted,
                      skipped: dupCount,
                    })}
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowDups((v) => !v)}
                    className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                  >
                    {showDups ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                    {showDups ? t("dup.hide") : t("dup.detail", { n: dupCount })}
                  </button>
                </div>
                {showDups && (
                  <ul className="mt-2 space-y-1 border-t border-[color:var(--warning)]/30 pt-2">
                    {(result.duplicates_skipped ?? []).map((d, i) => (
                      <li key={i} className="flex items-center justify-between gap-2 text-xs">
                        <span className="min-w-0 truncate text-muted-foreground">
                          {d.date} · {d.description}
                        </span>
                        <span className="tabular shrink-0">
                          {formatVnd(d.amount ?? 0)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {rows.length > 0 && (
              <ul className="max-h-[380px] divide-y divide-border overflow-y-auto scroll-thin">
                {rows.map((tx) => (
                  <li key={tx.id} className="flex items-center gap-3 py-2.5">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{tx.description}</p>
                      <p className="tabular text-xs text-muted-foreground">
                        {formatDateVn(tx.date)}
                      </p>
                    </div>
                    <EditableCategoryBadge
                      category={tx.category as Category}
                      size="sm"
                      onChange={(c) => onRecategorize(tx.id, c)}
                    />
                    <span
                      className={`tabular w-28 shrink-0 text-right text-sm font-semibold ${
                        tx.amount < 0 ? "text-foreground" : "text-[color:var(--positive)]"
                      }`}
                    >
                      {tx.amount < 0 ? "" : "+"}
                      {formatVnd(tx.amount)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button asChild className="flex-1">
                <Link to="/">
                  {t("csv.viewSummary")}
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button onClick={reset} variant="outline" className="flex-1">
                {t("csv.uploadAnother")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );

  function ChoiceRow({
    label,
    hint,
    onClick,
    primary,
    danger,
  }: {
    label: string;
    hint: string;
    onClick: () => void;
    primary?: boolean;
    danger?: boolean;
  }) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="flex w-full items-center gap-3 rounded-lg border border-border p-3 text-left transition-colors hover:border-ring hover:bg-secondary/50 active:scale-[.99]"
      >
        <div className="min-w-0 flex-1">
          <p
            className={`text-sm font-semibold ${
              danger ? "text-[color:var(--negative)]" : primary ? "text-primary" : ""
            }`}
          >
            {label}
          </p>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
        <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
      </button>
    );
  }
}
