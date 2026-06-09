import { Toaster as Sonner } from "sonner";
import { useTheme } from "@/context/theme";

export function Toaster() {
  const { resolved } = useTheme();
  return (
    <Sonner
      theme={resolved}
      position="bottom-right"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast: "font-sans rounded-lg border border-border",
        },
      }}
    />
  );
}
