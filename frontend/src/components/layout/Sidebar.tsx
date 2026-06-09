import { NavLink } from "react-router-dom";
import { Plus, CircleUser, LogOut } from "lucide-react";
import { Brand } from "./Brand";
import { NAV_ITEMS } from "./nav";
import { ThemeToggle, LangToggle } from "./Toggles";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useI18n } from "@/context/i18n";
import { useUi } from "@/context/ui";
import { useAuth } from "@/context/auth";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const { t } = useI18n();
  const { setQuickAddOpen } = useUi();
  const { status, user, logout } = useAuth();
  const accountLabel = user?.email ?? t("auth.guestMode");

  return (
    <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 self-start flex-col overflow-y-auto border-r border-border bg-card scroll-thin lg:flex">
      <div className="p-6">
        <Brand />
      </div>

      <div className="px-3">
        <Button
          className="w-full justify-start gap-2"
          onClick={() => setQuickAddOpen(true)}
          title={`${t("action.quickAdd")} · N`}
        >
          <Plus className="size-4" />
          {t("action.quickAdd")}
          <kbd className="ml-auto rounded border border-primary-foreground/30 px-1.5 text-[11px] font-medium opacity-80">
            N
          </kbd>
        </Button>
      </div>

      <nav className="mt-4 flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, labelKey, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
              )
            }
          >
            <Icon className="size-[18px]" />
            {t(labelKey)}
          </NavLink>
        ))}
      </nav>

      <Separator />
      <div className="px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2 text-sm">
            <CircleUser className="size-5 shrink-0 text-muted-foreground" />
            <div className="min-w-0">
              <p className="truncate font-medium leading-tight" title={accountLabel}>
                {accountLabel}
              </p>
              {status === "guest" && (
                <p className="text-[11px] leading-tight text-muted-foreground">
                  {t("auth.loggedInAs")}: {t("auth.guestMode")}
                </p>
              )}
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={logout}
            aria-label={status === "guest" ? t("auth.signIn") : t("auth.logout")}
            title={status === "guest" ? t("auth.signIn") : t("auth.logout")}
          >
            <LogOut className="size-4" />
          </Button>
        </div>
        <div className="mt-1 flex items-center">
          <LangToggle />
          <ThemeToggle />
        </div>
      </div>
    </aside>
  );
}
