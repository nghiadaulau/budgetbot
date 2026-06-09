import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, Trash2, Sun, Moon, Database, LogOut, CircleUser } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { useI18n } from "@/context/i18n";
import { useTheme } from "@/context/theme";
import { useAuth } from "@/context/auth";
import { useClearAll } from "@/hooks/useApi";
import { api, getUserId, isMock, setMock } from "@/api/client";
import { cn } from "@/lib/utils";

function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string; icon?: React.ReactNode }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg bg-muted p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            value === o.value
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground",
          )}
        >
          {o.icon}
          {o.label}
        </button>
      ))}
    </div>
  );
}

function Row({
  title,
  desc,
  children,
}: {
  title: string;
  desc: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="max-w-md">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{desc}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export default function Settings() {
  const { t, lang, setLang } = useI18n();
  const { theme, setTheme } = useTheme();
  const { status, user, logout } = useAuth();
  const qc = useQueryClient();
  const clearAll = useClearAll();

  const [mock, setMockState] = useState(isMock());

  const toggleMock = () => {
    const next = !mock;
    setMock(next);
    setMockState(next);
    qc.invalidateQueries();
    toast.success(t("settings.saved"));
  };

  const exportCsv = async () => {
    const rows = await api.listTransactions();
    const header = "date,description,amount,category,source";
    const body = rows
      .map(
        (r) =>
          `${r.date},"${r.description.replace(/"/g, '""')}",${r.amount},${r.category},${r.source ?? ""}`,
      )
      .join("\n");
    const blob = new Blob([`${header}\n${body}`], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `budgetbot-export-${getUserId()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(t("settings.exported"));
  };

  const onClearAll = () =>
    clearAll.mutate(undefined, {
      onSuccess: () => toast.success(t("settings.cleared")),
    });

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h2 className="text-h1">{t("settings.title")}</h2>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.profile")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-secondary text-muted-foreground">
                <CircleUser className="size-5" />
              </span>
              <div className="min-w-0">
                <p className="truncate font-medium">
                  {user?.email ?? t("auth.guestMode")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {status === "guest"
                    ? t("auth.guestModeHelp")
                    : `${t("auth.loggedInAs")} · ${getUserId()}`}
                </p>
              </div>
            </div>
            <Button variant="outline" onClick={logout} className="shrink-0">
              <LogOut className="size-4" />
              {status === "guest" ? t("auth.signIn") : t("auth.logout")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.appearance")}</CardTitle>
        </CardHeader>
        <CardContent className="divide-y divide-border py-0">
          <Row title={t("settings.theme")} desc="Light / Dark">
            <Segmented
              value={theme}
              onChange={setTheme}
              options={[
                {
                  value: "light",
                  label: t("settings.light"),
                  icon: <Sun className="size-4" />,
                },
                {
                  value: "dark",
                  label: t("settings.dark"),
                  icon: <Moon className="size-4" />,
                },
              ]}
            />
          </Row>
          <Row title={t("settings.language")} desc="Tiếng Việt / English">
            <Segmented
              value={lang}
              onChange={setLang}
              options={[
                { value: "vi", label: "Tiếng Việt" },
                { value: "en", label: "English" },
              ]}
            />
          </Row>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.backend")}</CardTitle>
        </CardHeader>
        <CardContent className="divide-y divide-border py-0">
          <Row title={t("settings.mockMode")} desc={t("settings.mockHelp")}>
            <button
              role="switch"
              aria-checked={mock}
              onClick={toggleMock}
              className={cn(
                "relative h-6 w-11 rounded-full transition-colors",
                mock ? "bg-primary" : "bg-muted",
              )}
            >
              <span
                className={cn(
                  "absolute top-0.5 size-5 rounded-full bg-white shadow transition-transform",
                  mock ? "translate-x-5" : "translate-x-0.5",
                )}
              />
            </button>
          </Row>
          <Row
            title="API URL"
            desc="VITE_API_URL"
          >
            <code className="flex items-center gap-1.5 rounded-md bg-muted px-2.5 py-1 text-xs">
              <Database className="size-3.5" />
              {import.meta.env.VITE_API_URL || "/api"}
            </code>
          </Row>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.data")}</CardTitle>
        </CardHeader>
        <CardContent className="divide-y divide-border py-0">
          <Row title={t("settings.exportCsv")} desc={t("settings.exportHelp")}>
            <Button variant="outline" onClick={exportCsv}>
              <Download className="size-4" />
              {t("settings.exportCsv")}
            </Button>
          </Row>
        </CardContent>
      </Card>

      <Card className="border-[color:var(--negative)]/40">
        <CardHeader>
          <CardTitle className="text-[color:var(--negative)]">
            {t("settings.danger")}
          </CardTitle>
          <CardDescription>{t("settings.clearHelp")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="destructive">
                <Trash2 className="size-4" />
                {t("settings.clearAll")}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t("settings.clearTitle")}</DialogTitle>
                <DialogDescription>
                  {t("settings.clearDesc")}
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline">{t("common.cancel")}</Button>
                </DialogClose>
                <DialogClose asChild>
                  <Button
                    variant="destructive"
                    onClick={onClearAll}
                    disabled={clearAll.isPending}
                  >
                    {t("settings.clearAll")}
                  </Button>
                </DialogClose>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </CardContent>
      </Card>
    </div>
  );
}
