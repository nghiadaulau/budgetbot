import type { ReactNode } from "react";
import { PiggyBank, Inbox } from "lucide-react";

interface Props {
  title: string;
  description?: string;
  icon?: ReactNode;
  /** Optional SVG illustration; takes precedence over `icon`. */
  illustration?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({
  title,
  description,
  icon,
  illustration,
  action,
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card/50 px-6 py-12 text-center">
      {illustration ? (
        <div className="mb-5">{illustration}</div>
      ) : (
        <div className="mb-4 grid size-16 place-items-center rounded-2xl bg-secondary text-muted-foreground">
          {icon ?? <PiggyBank className="size-8" />}
        </div>
      )}
      <h3 className="text-h2">{title}</h3>
      {description && (
        <p className="text-body mt-1.5 max-w-sm text-muted-foreground">
          {description}
        </p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

/** Compact in-card empty for charts (no data for the selected period). */
export function ChartEmpty({ message }: { message: string }) {
  return (
    <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-center">
      <Inbox className="size-7 text-muted-foreground/60" aria-hidden />
      <p className="text-body text-muted-foreground">{message}</p>
    </div>
  );
}
