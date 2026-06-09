import { formatVnd } from "@/lib/format";

interface TooltipPayload {
  name?: string;
  value?: number;
  payload?: { name?: string; label?: string; fill?: string; color?: string };
}

/** Shared themed tooltip — always renders amounts as VND. */
export function CurrencyTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  const title = p.payload?.label ?? p.payload?.name ?? p.name ?? label;
  const color = p.payload?.fill ?? p.payload?.color;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-sm shadow-md">
      <div className="flex items-center gap-2">
        {color && (
          <span
            className="size-2.5 rounded-full"
            style={{ backgroundColor: color }}
          />
        )}
        <span className="font-medium">{title}</span>
      </div>
      <div className="tabular mt-0.5 font-semibold">
        {formatVnd(Number(p.value ?? 0))}
      </div>
    </div>
  );
}
