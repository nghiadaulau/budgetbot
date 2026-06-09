import { useEffect, useMemo, useRef, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  ReceiptText,
  PieChart,
  Settings as SettingsIcon,
  FileSpreadsheet,
  FileText,
  Plus,
  MessageCircle,
  Moon,
  Sun,
  Languages,
  Search,
  type LucideIcon,
} from "lucide-react";
import { useUi } from "@/context/ui";
import { useI18n } from "@/context/i18n";
import { useTheme } from "@/context/theme";
import { cn } from "@/lib/utils";

interface Command {
  id: string;
  label: string;
  group: string;
  icon: LucideIcon;
  run: () => void;
}

export function CommandPalette() {
  const { commandOpen, setCommandOpen, setQuickAddOpen, setChatOpen } = useUi();
  const { t, lang, setLang } = useI18n();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  const close = () => setCommandOpen(false);
  const go = (path: string) => () => {
    navigate(path);
    close();
  };

  const commands: Command[] = useMemo(
    () => [
      { id: "nav-dash", group: t("cmdk.nav"), label: t("nav.dashboard"), icon: LayoutDashboard, run: go("/") },
      { id: "nav-txn", group: t("cmdk.nav"), label: t("nav.transactions"), icon: ReceiptText, run: go("/transactions") },
      { id: "nav-ins", group: t("cmdk.nav"), label: t("nav.insights"), icon: PieChart, run: go("/insights") },
      { id: "nav-set", group: t("cmdk.nav"), label: t("nav.settings"), icon: SettingsIcon, run: go("/settings") },
      { id: "act-quick", group: t("cmdk.actions"), label: t("action.quickAdd"), icon: Plus, run: () => { setQuickAddOpen(true); close(); } },
      { id: "act-csv", group: t("cmdk.actions"), label: t("action.uploadCsv"), icon: FileSpreadsheet, run: go("/upload") },
      { id: "act-pdf", group: t("cmdk.actions"), label: t("action.addReceipt"), icon: FileText, run: go("/receipt") },
      { id: "act-chat", group: t("cmdk.actions"), label: t("chat.open"), icon: MessageCircle, run: () => { setChatOpen(true); close(); } },
      { id: "act-theme", group: t("cmdk.actions"), label: theme === "dark" ? t("settings.light") : t("settings.dark"), icon: theme === "dark" ? Sun : Moon, run: () => { toggle(); close(); } },
      { id: "act-lang", group: t("cmdk.actions"), label: lang === "vi" ? "English" : "Tiếng Việt", icon: Languages, run: () => { setLang(lang === "vi" ? "en" : "vi"); close(); } },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, lang, theme],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(q));
  }, [commands, query]);

  useEffect(() => {
    if (commandOpen) {
      setQuery("");
      setActive(0);
    }
  }, [commandOpen]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      filtered[active]?.run();
    }
  };

  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(
      `[data-idx="${active}"]`,
    );
    el?.scrollIntoView({ block: "nearest" });
  }, [active]);

  let lastGroup = "";

  return (
    <DialogPrimitive.Root open={commandOpen} onOpenChange={setCommandOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="bb-overlay fixed inset-0 z-[60] bg-slate-950/50 backdrop-blur-sm" />
        <DialogPrimitive.Content
          onKeyDown={onKeyDown}
          className="bb-content fixed left-1/2 top-[14%] z-[60] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-popover shadow-xl"
        >
          <DialogPrimitive.Title className="sr-only">
            {t("cmdk.placeholder")}
          </DialogPrimitive.Title>
          <div className="flex items-center gap-2 border-b border-border px-3">
            <Search className="size-4 shrink-0 text-muted-foreground" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("cmdk.placeholder")}
              className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
          <div ref={listRef} className="max-h-[320px] overflow-y-auto p-2 scroll-thin">
            {filtered.length === 0 ? (
              <p className="px-2 py-6 text-center text-sm text-muted-foreground">
                {t("cmdk.empty")}
              </p>
            ) : (
              filtered.map((c, i) => {
                const header = c.group !== lastGroup ? c.group : null;
                lastGroup = c.group;
                const Icon = c.icon;
                return (
                  <div key={c.id}>
                    {header && (
                      <p className="text-caption px-2 pb-1 pt-2 text-muted-foreground">
                        {header}
                      </p>
                    )}
                    <button
                      type="button"
                      data-idx={i}
                      onMouseEnter={() => setActive(i)}
                      onClick={() => c.run()}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm transition-colors",
                        i === active
                          ? "bg-secondary text-foreground"
                          : "text-foreground/90",
                      )}
                    >
                      <Icon className="size-4 text-muted-foreground" />
                      {c.label}
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
