import { ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import {
  CATEGORIES,
  CATEGORY_META,
  categoryColor,
  type Category,
} from "@/lib/categories";
import { useI18n } from "@/context/i18n";
import { cn } from "@/lib/utils";

/** Soft tinted badge using the category's brand color (works light + dark). */
function tint(color: string) {
  return {
    color,
    backgroundColor: `${color}1f`,
    borderColor: `${color}40`,
  };
}

interface Props {
  category: Category;
  size?: "sm" | "md";
  className?: string;
}

export function CategoryBadge({ category, size = "md", className }: Props) {
  const { lang } = useI18n();
  const meta = CATEGORY_META[category];
  const Icon = meta.icon;
  return (
    <Badge
      style={tint(meta.color)}
      className={cn(size === "sm" && "px-2 py-0 text-[11px]", className)}
    >
      <Icon className="size-3.5" aria-hidden />
      {meta[lang]}
    </Badge>
  );
}

interface EditableProps extends Props {
  onChange: (next: Category) => void;
}

/** Click-to-recategorize badge: opens a dropdown of all categories. */
export function EditableCategoryBadge({
  category,
  onChange,
  size = "md",
  className,
}: EditableProps) {
  const { lang } = useI18n();
  const meta = CATEGORY_META[category];
  const Icon = meta.icon;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`${meta[lang]} — đổi danh mục`}
      >
        <Badge
          style={tint(meta.color)}
          className={cn(
            "cursor-pointer transition-opacity hover:opacity-80",
            size === "sm" && "px-2 py-0 text-[11px]",
            className,
          )}
        >
          <Icon className="size-3.5" aria-hidden />
          {meta[lang]}
          <ChevronDown className="size-3 opacity-70" aria-hidden />
        </Badge>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-72 overflow-y-auto">
        {CATEGORIES.map((c) => {
          const m = CATEGORY_META[c];
          const CIcon = m.icon;
          return (
            <DropdownMenuItem
              key={c}
              onSelect={() => c !== category && onChange(c)}
            >
              <CIcon
                className="size-4"
                style={{ color: categoryColor(c) }}
                aria-hidden
              />
              {m[lang]}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
