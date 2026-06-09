import { Plus } from "lucide-react";
import { useUi } from "@/context/ui";
import { useI18n } from "@/context/i18n";

/** Mobile-only floating Quick Add button, lifted clear of the bottom nav. */
export function Fab() {
  const { setQuickAddOpen } = useUi();
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={() => setQuickAddOpen(true)}
      aria-label={t("action.quickAdd")}
      className="fixed bottom-20 right-5 z-30 grid size-14 place-items-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform active:scale-95 lg:hidden"
    >
      <Plus className="size-6" />
    </button>
  );
}
