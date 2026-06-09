import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import * as cognito from "@/auth/cognito";
import { setUserId, setAuthToken, setMock } from "@/api/client";

type Status = "loading" | "authed" | "guest" | "unauthed";

interface AuthContextValue {
  status: Status;
  user: cognito.AuthUser | null;
  cognitoEnabled: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  confirm: (email: string, code: string) => Promise<void>;
  resendCode: (email: string) => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  confirmForgotPassword: (email: string, code: string, newPassword: string) => Promise<void>;
  continueAsGuest: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const GUEST_KEY = "budgetbot.guest";
const CHAT_KEY = "budgetbot.chat";

/** Drop locally-cached, user-specific UI state on any identity change. */
function clearUserScopedState() {
  localStorage.removeItem(CHAT_KEY);
}

/**
 * A real authenticated session must always show REAL backend data. The demo/mock
 * toggle (Settings) persists in localStorage and would otherwise silently replace
 * a logged-in user's real data with seeded fixtures — and survive logout/refresh.
 * Force it off whenever we resolve a genuine Cognito identity.
 */
function ensureRealDataForAuthed() {
  setMock(false);
}

function guestId(): string {
  let id = localStorage.getItem("budgetbot.guestId");
  if (!id) {
    id = `guest-${crypto.randomUUID().slice(0, 12)}`;
    localStorage.setItem("budgetbot.guestId", id);
  }
  return id;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<cognito.AuthUser | null>(null);

  useEffect(() => {
    let active = true;
    cognito.getCurrentUser().then((u) => {
      if (!active) return;
      if (u) {
        setUserId(u.sub);
        setAuthToken(u.idToken);
        ensureRealDataForAuthed();
        setUser(u);
        setStatus("authed");
      } else if (localStorage.getItem(GUEST_KEY) === "true") {
        setUserId(guestId());
        setAuthToken(null);
        setStatus("guest");
      } else {
        setStatus("unauthed");
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const u = await cognito.signIn(email, password);
      setUserId(u.sub);
      setAuthToken(u.idToken);
      ensureRealDataForAuthed();
      localStorage.removeItem(GUEST_KEY);
      clearUserScopedState();
      setUser(u);
      setStatus("authed");
      qc.clear();
    },
    [qc],
  );

  const continueAsGuest = useCallback(() => {
    localStorage.setItem(GUEST_KEY, "true");
    setUserId(guestId());
    setAuthToken(null);
    clearUserScopedState();
    setUser(null);
    setStatus("guest");
    qc.clear();
  }, [qc]);

  const logout = useCallback(() => {
    cognito.signOut();
    setAuthToken(null);
    localStorage.removeItem(GUEST_KEY);
    clearUserScopedState();
    setUser(null);
    setStatus("unauthed");
    qc.clear();
  }, [qc]);

  const value: AuthContextValue = {
    status,
    user,
    cognitoEnabled: cognito.cognitoEnabled,
    login,
    register: cognito.signUp,
    confirm: cognito.confirmSignUp,
    resendCode: cognito.resendCode,
    forgotPassword: cognito.forgotPassword,
    confirmForgotPassword: cognito.confirmForgotPassword,
    continueAsGuest,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
