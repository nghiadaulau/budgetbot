import { useRef, useState, type ReactNode } from "react";
import { UploadCloud } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/context/i18n";

interface Props {
  accept: string;
  onFile: (file: File) => void;
  title: string;
  hint: string;
  icon?: ReactNode;
}

/** Accessible drag-drop + click-to-browse file picker. */
export function Dropzone({ accept, onFile, title, hint, icon }: Props) {
  const { t } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file) onFile(file);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-14 text-center transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        dragging
          ? "border-ring bg-accent/40"
          : "border-border bg-card/50 hover:border-ring/60 hover:bg-secondary/40",
      )}
    >
      <span className="mb-4 grid size-14 place-items-center rounded-2xl bg-secondary text-foreground">
        {icon ?? <UploadCloud className="size-7" />}
      </span>
      <p className="font-semibold">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">
        {t("csv.or")}{" "}
        <span className="font-medium text-primary underline-offset-2">
          {t("csv.browse")}
        </span>
      </p>
      <p className="mt-3 text-xs text-muted-foreground">{hint}</p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
