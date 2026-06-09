import { FileSpreadsheet, FileText, PenLine } from "lucide-react";
import type { TxnSource } from "@/api/types";
import { useI18n } from "@/context/i18n";

const ICONS = {
  csv: FileSpreadsheet,
  pdf: FileText,
  manual: PenLine,
} as const;

export function SourceIcon({
  source = "csv",
  withLabel = false,
}: {
  source?: TxnSource;
  withLabel?: boolean;
}) {
  const { t } = useI18n();
  const Icon = ICONS[source] ?? FileSpreadsheet;
  const label = t(
    source === "pdf"
      ? "txn.source.pdf"
      : source === "manual"
        ? "txn.source.manual"
        : "txn.source.csv",
  );
  return (
    <span
      className="inline-flex items-center gap-1.5 text-muted-foreground"
      title={label}
    >
      <Icon className="size-4" aria-hidden />
      {withLabel ? <span className="text-xs">{label}</span> : (
        <span className="sr-only">{label}</span>
      )}
    </span>
  );
}
