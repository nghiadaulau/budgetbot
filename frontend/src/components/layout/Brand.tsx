import { useI18n } from "@/context/i18n";

export function Brand({ compact = false }: { compact?: boolean }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground">
        <svg viewBox="0 0 32 32" className="size-5" aria-hidden>
          <path
            d="M11 9h7.2a4.4 4.4 0 0 1 1 8.7A4.6 4.6 0 0 1 18.4 23H11V9Zm3.1 2.7v3.1h3.8a1.55 1.55 0 0 0 0-3.1h-3.8Zm0 5.6v3.2h4a1.6 1.6 0 0 0 0-3.2h-4Z"
            fill="currentColor"
          />
        </svg>
      </span>
      {!compact && (
        <div className="leading-tight">
          <div className="font-bold tracking-tight">{t("app.name")}</div>
          <div className="text-[11px] text-muted-foreground">AI Money Coach</div>
        </div>
      )}
    </div>
  );
}
