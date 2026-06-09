import { useLocation } from "react-router-dom";
import { MessageCircle, Search } from "lucide-react";
import { Brand } from "./Brand";
import { MonthPicker } from "./MonthPicker";
import { ThemeToggle, LangToggle } from "./Toggles";
import { NAV_ITEMS } from "./nav";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/context/i18n";
import { useUi } from "@/context/ui";

export function Header() {
  const { t } = useI18n();
  const { setChatOpen, setCommandOpen } = useUi();
  const { pathname } = useLocation();
  const active =
    NAV_ITEMS.find((n) => (n.to === "/" ? pathname === "/" : pathname.startsWith(n.to))) ??
    NAV_ITEMS[0];

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur lg:px-8">
      <div className="lg:hidden">
        <Brand compact />
      </div>
      <h1 className="hidden text-h2 lg:block">{t(active.labelKey)}</h1>

      <div className="ml-auto flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => setCommandOpen(true)}
          className="hidden h-9 items-center gap-2 rounded-md border border-border bg-card px-3 text-sm text-muted-foreground transition-colors hover:bg-secondary lg:flex"
        >
          <Search className="size-4" />
          {t("common.search")}
          <kbd className="ml-2 rounded border border-border bg-muted px-1.5 py-0.5 text-[11px] font-medium">
            ⌘K
          </kbd>
        </button>
        <MonthPicker />
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={() => setChatOpen(true)}
          aria-label={t("chat.open")}
        >
          <MessageCircle className="size-5" />
        </Button>
        <div className="lg:hidden">
          <LangToggle />
        </div>
        <div className="lg:hidden">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
