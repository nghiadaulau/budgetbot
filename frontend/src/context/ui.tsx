import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { currentMonth } from "@/lib/format";

interface UiContextValue {
  /** Selected month "YYYY-MM" — shared by the header picker and all pages. */
  month: string;
  setMonth: (m: string) => void;
  quickAddOpen: boolean;
  setQuickAddOpen: (open: boolean) => void;
  /** AI money-coach chat panel. */
  chatOpen: boolean;
  setChatOpen: (open: boolean) => void;
  /** Cmd/Ctrl+K command palette. */
  commandOpen: boolean;
  setCommandOpen: (open: boolean) => void;
}

const UiContext = createContext<UiContextValue | null>(null);

export function UiProvider({ children }: { children: ReactNode }) {
  const [month, setMonth] = useState<string>(currentMonth());
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  return (
    <UiContext.Provider
      value={{
        month,
        setMonth,
        quickAddOpen,
        setQuickAddOpen,
        chatOpen,
        setChatOpen,
        commandOpen,
        setCommandOpen,
      }}
    >
      {children}
    </UiContext.Provider>
  );
}

export function useUi(): UiContextValue {
  const ctx = useContext(UiContext);
  if (!ctx) throw new Error("useUi must be used within UiProvider");
  return ctx;
}
