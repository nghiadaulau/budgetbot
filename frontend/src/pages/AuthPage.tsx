import { useState, useEffect, type FormEvent } from "react";
import { toast } from "sonner";
import { api } from "@/api/client";
import { Eye, EyeOff, Loader2, ArrowLeft, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Brand } from "@/components/layout/Brand";
import { ThemeToggle, LangToggle } from "@/components/layout/Toggles";
import { useAuth } from "@/context/auth";
import { useI18n } from "@/context/i18n";

type Mode = "login" | "register" | "confirm" | "forgot" | "forgotConfirm";

/** Map common Cognito errors to friendly localized messages. */
function authError(err: unknown, t: (k: never) => string): string {
  const name = (err as { name?: string })?.name || "";
  const map: Record<string, string> = {
    NotAuthorizedException: "auth.err.credentials",
    UserNotFoundException: "auth.err.credentials",
    UsernameExistsException: "auth.err.exists",
    CodeMismatchException: "auth.err.code",
    ExpiredCodeException: "auth.err.codeExpired",
    InvalidPasswordException: "auth.err.password",
    LimitExceededException: "auth.err.limit",
    UserNotConfirmedException: "auth.err.notConfirmed",
  };
  const key = map[name] || "auth.err.generic";
  // @ts-expect-error key is a valid StringKey at runtime
  return t(key);
}

function PasswordField({
  id, label, value, onChange, autoComplete,
}: {
  id: string; label: string; value: string;
  onChange: (v: string) => void; autoComplete: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <Input
          id={id}
          type={show ? "text" : "password"}
          autoComplete={autoComplete}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="pr-10"
          required
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          aria-label={show ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
    </div>
  );
}

export default function AuthPage() {
  const { t } = useI18n();
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [authRequired, setAuthRequired] = useState(false);

  useEffect(() => {
    api.health().then((h) => setAuthRequired(!!h.require_auth)).catch(() => {});
  }, []);

  const reset = (m: Mode) => {
    setMode(m);
    setError("");
    setPassword("");
    setConfirmPw("");
    setCode("");
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (mode === "register" && password !== confirmPw) {
      setError(t("auth.err.mismatch"));
      return;
    }
    setBusy(true);
    try {
      if (mode === "login") {
        await auth.login(email, password);
      } else if (mode === "register") {
        await auth.register(email, password);
        toast.success(t("auth.codeSent"));
        reset("confirm");
        setEmail(email);
      } else if (mode === "confirm") {
        await auth.confirm(email, code);
        toast.success(t("auth.confirmed"));
        reset("login");
      } else if (mode === "forgot") {
        await auth.forgotPassword(email);
        toast.success(t("auth.codeSent"));
        reset("forgotConfirm");
        setEmail(email);
      } else if (mode === "forgotConfirm") {
        await auth.confirmForgotPassword(email, code, password);
        toast.success(t("auth.pwReset"));
        reset("login");
      }
    } catch (err) {
      const name = (err as { name?: string })?.name;
      if (name === "UserNotConfirmedException") {
        reset("confirm");
        toast.info(t("auth.needConfirm"));
      }
      setError(authError(err, t as never));
    } finally {
      setBusy(false);
    }
  }

  const titles: Record<Mode, [string, string]> = {
    login: [t("auth.login.title"), t("auth.login.sub")],
    register: [t("auth.register.title"), t("auth.register.sub")],
    confirm: [t("auth.confirm.title"), t("auth.confirm.sub")],
    forgot: [t("auth.forgot.title"), t("auth.forgot.sub")],
    forgotConfirm: [t("auth.forgotConfirm.title"), t("auth.forgotConfirm.sub")],
  };
  const [title, sub] = titles[mode];
  const cta: Record<Mode, string> = {
    login: t("auth.login.cta"),
    register: t("auth.register.cta"),
    confirm: t("auth.confirm.cta"),
    forgot: t("auth.forgot.cta"),
    forgotConfirm: t("auth.forgotConfirm.cta"),
  };

  return (
    <div className="relative flex min-h-dvh items-center justify-center bg-background px-4 py-10">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-primary/10 to-transparent"
      />
      <div className="absolute right-4 top-4 flex items-center">
        <LangToggle />
        <ThemeToggle />
      </div>

      <div className="relative w-full max-w-sm">
        <div className="mb-6 flex justify-center">
          <Brand />
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
          {mode !== "login" && mode !== "register" && (
            <button
              type="button"
              onClick={() => reset(mode === "forgotConfirm" ? "forgot" : "login")}
              className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="size-4" /> {t("common.back")}
            </button>
          )}

          <h1 className="text-h1">{title}</h1>
          <p className="text-body mt-1 text-muted-foreground">{sub}</p>

          {!auth.cognitoEnabled && (
            <p className="text-body mt-3 rounded-lg border border-[color:var(--warning)]/40 bg-[color:var(--warning)]/10 p-2 text-xs">
              {t("auth.notConfigured")}
            </p>
          )}

          <form onSubmit={onSubmit} className="mt-5 space-y-4">
            {mode !== "confirm" && mode !== "forgotConfirm" && (
              <div className="space-y-1.5">
                <Label htmlFor="auth-email">{t("auth.email")}</Label>
                <Input
                  id="auth-email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                />
              </div>
            )}

            {(mode === "confirm" || mode === "forgotConfirm") && (
              <>
                <div className="space-y-1.5">
                  <Label htmlFor="auth-email-ro">{t("auth.email")}</Label>
                  <Input id="auth-email-ro" value={email} readOnly className="opacity-70" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="auth-code">{t("auth.code")}</Label>
                  <Input
                    id="auth-code"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="123456"
                    required
                  />
                </div>
              </>
            )}

            {(mode === "login" || mode === "register" || mode === "forgotConfirm") && (
              <PasswordField
                id="auth-password"
                label={mode === "forgotConfirm" ? t("auth.newPassword") : t("auth.password")}
                value={password}
                onChange={setPassword}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
              />
            )}

            {mode === "register" && (
              <PasswordField
                id="auth-confirm"
                label={t("auth.confirmPassword")}
                value={confirmPw}
                onChange={setConfirmPw}
                autoComplete="new-password"
              />
            )}

            {mode === "login" && (
              <button
                type="button"
                onClick={() => reset("forgot")}
                className="text-xs text-primary hover:underline"
              >
                {t("auth.forgotLink")}
              </button>
            )}

            {error && (
              <p
                role="alert"
                aria-live="polite"
                className="flex items-center gap-1.5 text-sm text-[color:var(--negative)]"
              >
                <AlertCircle className="size-4 shrink-0" /> {error}
              </p>
            )}

            <Button type="submit" className="w-full" size="lg" disabled={busy}>
              {busy && <Loader2 className="size-4 animate-spin" />}
              {cta[mode]}
            </Button>
          </form>

          {mode === "confirm" && (
            <button
              type="button"
              onClick={() => auth.resendCode(email).then(() => toast.success(t("auth.codeSent")))}
              className="mt-3 text-xs text-primary hover:underline"
            >
              {t("auth.resend")}
            </button>
          )}

          {(mode === "login" || mode === "register") && (
            <p className="text-body mt-4 text-center text-muted-foreground">
              {mode === "login" ? t("auth.noAccount") : t("auth.haveAccount")}{" "}
              <button
                type="button"
                onClick={() => reset(mode === "login" ? "register" : "login")}
                className="font-medium text-primary hover:underline"
              >
                {mode === "login" ? t("auth.register.cta") : t("auth.login.cta")}
              </button>
            </p>
          )}

          {!authRequired && (
            <>
              <div className="my-4 flex items-center gap-3">
                <Separator className="flex-1" />
                <span className="text-xs text-muted-foreground">{t("common.or")}</span>
                <Separator className="flex-1" />
              </div>

              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={auth.continueAsGuest}
              >
                {t("auth.guest")}
              </Button>
            </>
          )}
        </div>

        <p className="text-body mt-4 text-center text-xs text-muted-foreground">
          {t("app.tagline")}
        </p>
      </div>
    </div>
  );
}
