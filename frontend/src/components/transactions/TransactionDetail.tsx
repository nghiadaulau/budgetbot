import { useState } from "react";
import { toast } from "sonner";
import { Trash2, HelpCircle, Loader2 } from "lucide-react";
import { api } from "@/api/client";
import type { AuditEntry } from "@/api/types";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerFooter,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { EditableCategoryBadge } from "@/components/CategoryBadge";
import { SourceIcon } from "./SourceIcon";
import { useI18n } from "@/context/i18n";
import { useIsDesktop } from "@/hooks/useMediaQuery";
import { useUpdateCategory, useDeleteTransaction } from "@/hooks/useApi";
import type { Transaction } from "@/api/types";
import type { Category } from "@/lib/categories";
import { formatVnd, formatDateLong } from "@/lib/format";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-right text-sm font-medium">{children}</span>
    </div>
  );
}

export function TransactionDetail({
  txn,
  open,
  onClose,
}: {
  txn: Transaction | null;
  open: boolean;
  onClose: () => void;
}) {
  const { t, lang } = useI18n();
  const isDesktop = useIsDesktop();
  const updateCat = useUpdateCategory();
  const del = useDeleteTransaction();
  const [confirming, setConfirming] = useState(false);
  const [audit, setAudit] = useState<AuditEntry | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);

  if (!txn) return null;

  const loadAudit = async () => {
    setAuditLoading(true);
    try {
      const res = await api.getAudit(txn.id);
      setAudit(res.audit[0] ?? null);
    } finally {
      setAuditLoading(false);
    }
  };

  const sourceLabel = (s: string) =>
    t(`txn.whySource.${s}` as "txn.whySource.llm") || s;

  const onDelete = () => {
    del.mutate(txn.id, {
      onSuccess: () => {
        toast.success(t("txn.deleted"));
        setConfirming(false);
        onClose();
      },
    });
  };

  return (
    <Drawer
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setConfirming(false);
          setAudit(null);
          onClose();
        }
      }}
      direction={isDesktop ? "right" : "bottom"}
    >
      <DrawerContent direction={isDesktop ? "right" : "bottom"}>
        <DrawerHeader>
          <DrawerTitle>{t("txn.detailTitle")}</DrawerTitle>
        </DrawerHeader>

        <div className="flex-1 overflow-y-auto px-6">
          <p className="text-base font-semibold">{txn.description}</p>
          <p
            className={`tabular mt-1 text-2xl font-semibold ${
              txn.amount < 0
                ? "text-foreground"
                : "text-[color:var(--positive)]"
            }`}
          >
            {txn.amount < 0 ? "" : "+"}
            {formatVnd(txn.amount)}
          </p>

          <Separator className="my-3" />

          <Field label={t("common.date")}>
            <span className="tabular">{formatDateLong(txn.date, lang)}</span>
          </Field>
          <Field label={t("common.category")}>
            <EditableCategoryBadge
              category={txn.category as Category}
              size="sm"
              onChange={(c) =>
                updateCat.mutate(
                  { id: txn.id, category: c },
                  {
                    onSuccess: () => toast.success(t("txn.categoryUpdated")),
                    onError: () => toast.error(t("txn.updateFailed")),
                  },
                )
              }
            />
          </Field>
          <Field label={t("common.source")}>
            <SourceIcon source={txn.source} withLabel />
          </Field>
          {txn.confidence && (
            <Field label={t("txn.confidence")}>
              <span className="capitalize">{txn.confidence}</span>
            </Field>
          )}

          <Separator className="my-3" />
          {audit ? (
            <div className="rounded-lg bg-secondary/50 p-3 text-sm">
              <p className="font-medium">{sourceLabel(audit.source)}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {t("txn.whyModel")}: {audit.model_id ?? "—"} · {t("txn.whyVersion")}:{" "}
                {audit.prompt_version ?? "—"}
              </p>
            </div>
          ) : (
            <button
              type="button"
              onClick={loadAudit}
              disabled={auditLoading}
              className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline disabled:opacity-60"
            >
              {auditLoading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <HelpCircle className="size-4" />
              )}
              {t("txn.why")}
            </button>
          )}
        </div>

        <DrawerFooter>
          {confirming ? (
            <div className="flex gap-2">
              <Button
                variant="destructive"
                className="flex-1"
                onClick={onDelete}
                disabled={del.isPending}
              >
                {t("txn.deleteConfirm")}
              </Button>
              <Button
                variant="outline"
                onClick={() => setConfirming(false)}
              >
                {t("common.cancel")}
              </Button>
            </div>
          ) : (
            <Button
              variant="outline"
              className="text-[color:var(--negative)]"
              onClick={() => setConfirming(true)}
            >
              <Trash2 className="size-4" />
              {t("common.delete")}
            </Button>
          )}
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
