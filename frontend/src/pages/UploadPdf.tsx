import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileText,
  Loader2,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Sparkles,
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Dropzone } from "@/components/Dropzone";
import { PageHeader } from "@/components/layout/PageHeader";
import { useI18n } from "@/context/i18n";
import { useCreateTransaction } from "@/hooks/useApi";
import { api } from "@/api/client";
import type { ReceiptExtraction } from "@/api/types";
import {
  CATEGORIES,
  CATEGORY_META,
  categoryColor,
} from "@/lib/categories";
import { formatVnd, formatThousands, formatDateVn } from "@/lib/format";

type Phase = "idle" | "reading" | "review" | "error";

export default function UploadPdf() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const create = useCreateTransaction();

  const [phase, setPhase] = useState<Phase>("idle");
  const [data, setData] = useState<ReceiptExtraction | null>(null);
  const [showItems, setShowItems] = useState(false);

  async function run(file: File) {
    const ok = /\.(pdf|png|jpe?g|webp)$/i.test(file.name) ||
      file.type === "application/pdf" || file.type.startsWith("image/");
    if (!ok) {
      setPhase("error");
      return;
    }
    setPhase("reading");
    try {
      const res = await api.uploadPdf(file);
      setData(res);
      setPhase("review");
    } catch {
      setPhase("error");
    }
  }

  const onConfirm = async () => {
    if (!data) return;
    try {
      await create.mutateAsync({
        date: data.date,
        description: data.merchant,
        amount: data.amount,
        category: data.category,
        source: "pdf",
      });
      toast.success(t("pdf.saved"));
      navigate("/");
    } catch {
      toast.error(t("csv.errorAi"));
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title={t("pdf.title")} subtitle={t("pdf.subtitle")} />

      {phase === "idle" && (
        <Dropzone
          accept="application/pdf,.pdf,image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
          onFile={run}
          title={t("pdf.dropHere")}
          hint={t("pdf.supports")}
          icon={<FileText className="size-7" />}
        />
      )}

      {phase === "error" && (
        <Card className="border-[color:var(--negative)]/40">
          <CardContent className="flex items-start gap-3 p-6">
            <AlertTriangle className="mt-0.5 size-5 shrink-0 text-[color:var(--negative)]" />
            <div className="flex-1">
              <p className="font-medium">{t("csv.errorAi")}</p>
              <Button
                onClick={() => setPhase("idle")}
                variant="outline"
                size="sm"
                className="mt-3"
              >
                {t("common.retry")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {phase === "reading" && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14">
            <Loader2 className="size-7 animate-spin text-primary" />
            <p className="font-medium">{t("pdf.reading")}</p>
          </CardContent>
        </Card>
      )}

      {phase === "review" && data && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkles className="size-5 text-primary" />
              <CardTitle>{t("pdf.title")}</CardTitle>
            </div>
            <CardDescription>
              {t("csv.costHint", {
                cost: `$${(data.ai_cost_usd ?? 0.004).toFixed(3)}`,
              })}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!!data.warnings?.length && (
              <div className="space-y-2">
                {data.warnings.map((w, i) => (
                  <div
                    key={i}
                    role="alert"
                    aria-live="polite"
                    className="flex items-start gap-2 rounded-lg border border-[color:var(--warning)]/50 bg-[color:var(--warning)]/10 p-3 text-sm"
                  >
                    <AlertTriangle className="mt-0.5 size-4 shrink-0 text-[color:var(--warning)]" />
                    <span className="text-muted-foreground">{w.message}</span>
                  </div>
                ))}
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="r-merchant">{t("pdf.merchant")}</Label>
              <Input
                id="r-merchant"
                value={data.merchant}
                onChange={(e) =>
                  setData({ ...data, merchant: e.target.value })
                }
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="r-date">{t("common.date")}</Label>
                <Input
                  id="r-date"
                  type="date"
                  value={data.date}
                  onChange={(e) => setData({ ...data, date: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="r-amount">{t("common.amount")} (₫)</Label>
                <Input
                  id="r-amount"
                  inputMode="numeric"
                  className="tabular"
                  value={formatThousands(Math.abs(data.amount))}
                  onChange={(e) => {
                    const digits = Number(e.target.value.replace(/\D/g, "")) || 0;
                    setData({ ...data, amount: -digits });
                  }}
                />
              </div>
            </div>

            {data.items.length > 0 && (
              <div className="rounded-lg border border-border">
                <button
                  type="button"
                  onClick={() => setShowItems((v) => !v)}
                  className="flex w-full items-center justify-between px-3 py-2.5 text-sm font-medium"
                >
                  <span>{t("pdf.items", { n: data.items.length })}</span>
                  {showItems ? (
                    <ChevronDown className="size-4" />
                  ) : (
                    <ChevronRight className="size-4" />
                  )}
                </button>
                {showItems && (
                  <>
                    <Separator />
                    <ul className="divide-y divide-border">
                      {data.items.map((it, i) => (
                        <li
                          key={i}
                          className="flex items-center justify-between px-3 py-2 text-sm"
                        >
                          <span className="text-muted-foreground">
                            {it.name}
                          </span>
                          <span className="tabular">
                            {formatVnd(Math.abs(it.amount))}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}

            <div className="space-y-2">
              <Label>{t("pdf.suggestedCategory")}</Label>
              <div className="flex flex-wrap gap-2">
                {CATEGORIES.map((c) => {
                  const meta = CATEGORY_META[c];
                  const Icon = meta.icon;
                  const active = data.category === c;
                  return (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setData({ ...data, category: c })}
                      className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors"
                      style={
                        active
                          ? {
                              color: categoryColor(c),
                              backgroundColor: `${categoryColor(c)}1f`,
                              borderColor: `${categoryColor(c)}80`,
                            }
                          : undefined
                      }
                    >
                      <Icon className="size-3.5" />
                      {meta[lang]}
                    </button>
                  );
                })}
              </div>
            </div>

            <Separator />
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                {formatDateVn(data.date)}
              </span>
              <span className="tabular text-lg font-semibold">
                {formatVnd(data.amount)}
              </span>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <Button
                onClick={onConfirm}
                className="flex-1"
                disabled={create.isPending}
              >
                {create.isPending ? t("common.saving") : t("pdf.confirm")}
              </Button>
              <Button
                variant="outline"
                onClick={() => setPhase("idle")}
                className="flex-1"
              >
                {t("common.cancel")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
