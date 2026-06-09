import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Sparkles, ArrowDownLeft, ArrowUpRight, AlertTriangle } from "lucide-react";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerFooter,
  DrawerTitle,
  DrawerDescription,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { useUi } from "@/context/ui";
import { useI18n } from "@/context/i18n";
import { useIsDesktop } from "@/hooks/useMediaQuery";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { DuplicateWarning, TransactionInput } from "@/api/types";
import {
  CATEGORIES,
  CATEGORY_META,
  suggestCategory,
  type Category,
} from "@/lib/categories";
import { formatThousands, todayIso, formatDateVn, formatVnd } from "@/lib/format";
import { cn } from "@/lib/utils";

const schema = z.object({
  magnitude: z.coerce.number().positive(),
  description: z.string().trim().min(1),
  date: z.string().min(1),
  category: z.enum(CATEGORIES),
  kind: z.enum(["expense", "income"]),
});
type FormValues = z.infer<typeof schema>;

export function QuickAddDrawer() {
  const { quickAddOpen, setQuickAddOpen } = useUi();
  const { t, lang } = useI18n();
  const isDesktop = useIsDesktop();
  const qc = useQueryClient();
  const categoryTouched = useRef(false);
  const [amountText, setAmountText] = useState("");
  const [saving, setSaving] = useState(false);
  const [warning, setWarning] = useState<DuplicateWarning | null>(null);
  const pendingInput = useRef<TransactionInput | null>(null);

  const {
    control,
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      magnitude: undefined as unknown as number,
      description: "",
      date: todayIso(),
      category: "Other",
      kind: "expense",
    },
  });

  const description = watch("description");
  const kind = watch("kind");
  const magnitude = watch("magnitude");

  useEffect(() => {
    if (categoryTouched.current || !description) return;
    const signed = kind === "income" ? 1 : -1;
    setValue("category", suggestCategory(description, signed));
  }, [description, kind, setValue]);

  useEffect(() => {
    setWarning(null);
  }, [description, kind, magnitude]);

  useEffect(() => {
    if (quickAddOpen) {
      categoryTouched.current = false;
      setAmountText("");
      setWarning(null);
      pendingInput.current = null;
      reset({
        magnitude: undefined as unknown as number,
        description: "",
        date: todayIso(),
        category: "Other",
        kind: "expense",
      });
    }
  }, [quickAddOpen, reset]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["transactions"] });
    qc.invalidateQueries({ queryKey: ["summary"] });
    qc.invalidateQueries({ queryKey: ["budgets"] });
  };

  const finishSaved = () => {
    toast.success(t("quickAdd.saved"));
    invalidate();
    setWarning(null);
    pendingInput.current = null;
    setQuickAddOpen(false);
  };

  const onSubmit = async (v: FormValues) => {
    const input: TransactionInput = {
      date: v.date,
      description: v.description,
      amount: v.kind === "income" ? v.magnitude : -v.magnitude,
      category: v.category,
      source: "manual",
    };
    setSaving(true);
    try {
      const outcome = await api.createTransactionChecked(input);
      if (outcome.kind === "warning") {
        pendingInput.current = input;
        setWarning(outcome.warning);
      } else {
        finishSaved();
      }
    } catch {
      toast.error(t("csv.errorAi"));
    } finally {
      setSaving(false);
    }
  };

  const saveAnyway = async () => {
    const input = pendingInput.current;
    if (!input) return;
    setSaving(true);
    try {
      await api.createTransaction(input);
      finishSaved();
    } catch {
      toast.error(t("csv.errorAi"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer
      open={quickAddOpen}
      onOpenChange={setQuickAddOpen}
      direction={isDesktop ? "right" : "bottom"}
    >
      <DrawerContent direction={isDesktop ? "right" : "bottom"}>
        <DrawerHeader>
          <DrawerTitle>{t("quickAdd.title")}</DrawerTitle>
          <DrawerDescription>{t("quickAdd.desc")}</DrawerDescription>
        </DrawerHeader>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="flex flex-1 flex-col gap-5 overflow-y-auto px-6 pb-2"
        >
          <Controller
            control={control}
            name="kind"
            render={({ field }) => (
              <div className="grid grid-cols-2 gap-3">
                {(
                  [
                    {
                      k: "expense" as const,
                      label: t("quickAdd.expense"),
                      Icon: ArrowDownLeft,
                      color: "var(--negative)",
                    },
                    {
                      k: "income" as const,
                      label: t("quickAdd.income"),
                      Icon: ArrowUpRight,
                      color: "var(--positive)",
                    },
                  ]
                ).map(({ k, label, Icon, color }) => {
                  const selected = field.value === k;
                  return (
                    <button
                      key={k}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => field.onChange(k)}
                      className={cn(
                        "flex items-center justify-center gap-2 rounded-lg border-2 py-2.5 text-sm font-semibold transition-colors",
                        selected
                          ? "text-[color:var(--_c)]"
                          : "border-border text-muted-foreground hover:bg-secondary",
                      )}
                      style={
                        selected
                          ? ({
                              ["--_c" as string]: color,
                              borderColor: color,
                              backgroundColor: `color-mix(in srgb, ${color} 14%, transparent)`,
                            } as CSSProperties)
                          : undefined
                      }
                    >
                      <Icon className="size-4" />
                      {label}
                    </button>
                  );
                })}
              </div>
            )}
          />

          <div className="space-y-1.5">
            <Label htmlFor="qa-amount">{t("quickAdd.amount")}</Label>
            <div className="relative">
              <span
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-2xl font-semibold tabular"
                style={{
                  color:
                    kind === "income"
                      ? "var(--positive)"
                      : "var(--negative)",
                }}
              >
                {kind === "income" ? "+" : "−"}
              </span>
              <Controller
                control={control}
                name="magnitude"
                render={({ field }) => (
                  <Input
                    id="qa-amount"
                    inputMode="numeric"
                    autoComplete="off"
                    placeholder="0"
                    value={amountText}
                    onChange={(e) => {
                      const digits = e.target.value.replace(/\D/g, "");
                      setAmountText(digits ? formatThousands(digits) : "");
                      field.onChange(digits ? Number(digits) : undefined);
                    }}
                    className="tabular h-14 pl-9 pr-10 text-2xl font-semibold"
                    aria-invalid={!!errors.magnitude}
                  />
                )}
              />
              <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-lg text-muted-foreground">
                ₫
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              {t("quickAdd.amountHint")}
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="qa-desc">{t("common.description")}</Label>
            <Input
              id="qa-desc"
              autoFocus
              placeholder={t("quickAdd.descPlaceholder")}
              aria-invalid={!!errors.description}
              {...register("description")}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="qa-date">{t("common.date")}</Label>
              <Input id="qa-date" type="date" {...register("date")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="qa-cat">{t("common.category")}</Label>
              <Controller
                control={control}
                name="category"
                render={({ field }) => (
                  <Select
                    value={field.value}
                    onValueChange={(v) => {
                      categoryTouched.current = true;
                      field.onChange(v as Category);
                    }}
                  >
                    <SelectTrigger id="qa-cat">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CATEGORIES.map((c) => (
                        <SelectItem key={c} value={c}>
                          {CATEGORY_META[c][lang]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          {!categoryTouched.current && description && (
            <p className="-mt-2 flex items-center gap-1 text-xs text-muted-foreground">
              <Sparkles className="size-3.5" />
              {t("quickAdd.categoryAuto")}
            </p>
          )}
        </form>

        <DrawerFooter>
          {warning && (
            <div
              role="alert"
              aria-live="polite"
              className="rounded-lg border border-[color:var(--warning)]/50 bg-[color:var(--warning)]/10 p-3"
            >
              <p className="flex items-center gap-1.5 text-sm font-medium text-[color:var(--warning)]">
                <AlertTriangle className="size-4" />
                {t("dup.warnTitle")}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {warning.message}
              </p>
              {!!warning.matching_transactions?.length && (
                <ul className="mt-2 space-y-1 border-t border-[color:var(--warning)]/30 pt-2">
                  {warning.matching_transactions.map((m) => (
                    <li
                      key={m.id}
                      className="flex items-center justify-between gap-2 text-xs"
                    >
                      <span className="min-w-0 truncate text-muted-foreground">
                        {formatDateVn(m.date)} · {m.description}
                      </span>
                      <span className="tabular shrink-0">{formatVnd(m.amount)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {warning ? (
            <div className="flex gap-2">
              <Button
                onClick={saveAnyway}
                disabled={saving}
                variant="outline"
                className="flex-1 text-[color:var(--warning)]"
                size="lg"
              >
                {saving ? t("common.saving") : t("dup.saveAnyway")}
              </Button>
              <Button onClick={() => setWarning(null)} variant="ghost" size="lg">
                {t("common.cancel")}
              </Button>
            </div>
          ) : (
            <Button
              onClick={handleSubmit(onSubmit)}
              disabled={saving}
              className="w-full"
              size="lg"
            >
              {saving ? t("common.saving") : t("common.save")}
            </Button>
          )}
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
