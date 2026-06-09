import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useUi } from "@/context/ui";

/** True when focus is in a field where typing should not trigger shortcuts. */
function isTyping(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null;
  if (!node) return false;
  const tag = node.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    node.isContentEditable
  );
}

/**
 * Global keyboard layer (Linear-style):
 *   ⌘/Ctrl+K or /  → command palette
 *   n              → Quick Add
 *   g then d/t/i/s → go to Dashboard / Transactions / Insights / Settings
 */
export function useKeyboardShortcuts() {
  const navigate = useNavigate();
  const { setCommandOpen, setQuickAddOpen } = useUi();
  const gPending = useRef(false);
  const gTimer = useRef<number | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen(true);
        return;
      }
      if (isTyping(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;

      if (gPending.current) {
        const map: Record<string, string> = {
          d: "/",
          t: "/transactions",
          i: "/insights",
          s: "/settings",
        };
        const dest = map[e.key.toLowerCase()];
        if (dest) {
          e.preventDefault();
          navigate(dest);
        }
        gPending.current = false;
        if (gTimer.current) window.clearTimeout(gTimer.current);
        return;
      }

      if (e.key === "/") {
        e.preventDefault();
        setCommandOpen(true);
      } else if (e.key.toLowerCase() === "n") {
        e.preventDefault();
        setQuickAddOpen(true);
      } else if (e.key.toLowerCase() === "g") {
        gPending.current = true;
        if (gTimer.current) window.clearTimeout(gTimer.current);
        gTimer.current = window.setTimeout(() => {
          gPending.current = false;
        }, 1200);
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, setCommandOpen, setQuickAddOpen]);
}
