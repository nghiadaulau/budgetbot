import { Moon, Sun, Languages } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/context/theme";
import { useI18n } from "@/context/i18n";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      aria-label={theme === "dark" ? "Chuyển sáng" : "Chuyển tối"}
      title={theme === "dark" ? "Light" : "Dark"}
    >
      {theme === "dark" ? (
        <Sun className="size-5" />
      ) : (
        <Moon className="size-5" />
      )}
    </Button>
  );
}

export function LangToggle() {
  const { lang, setLang } = useI18n();
  return (
    <Button
      variant="ghost"
      size="sm"
      className="gap-1.5"
      onClick={() => setLang(lang === "vi" ? "en" : "vi")}
      aria-label="Đổi ngôn ngữ / Switch language"
    >
      <Languages className="size-4" />
      <span className="font-semibold uppercase">{lang}</span>
    </Button>
  );
}
