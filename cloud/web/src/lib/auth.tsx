import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setUnauthorizedHandler, tokenStore } from "./api";
import type { Me } from "./types";

type Status = "loading" | "authed" | "anon";

interface AuthValue {
  status: Status;
  me: Me | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>(tokenStore.get() ? "loading" : "anon");
  const [me, setMe] = useState<Me | null>(null);

  const logout = useCallback(() => {
    tokenStore.clear();
    setMe(null);
    setStatus("anon");
  }, []);

  // A 401 from any request (expired/invalid token) drops us back to anonymous.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setMe(null);
      setStatus("anon");
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  // On first load, validate an existing token by fetching the profile.
  useEffect(() => {
    if (!tokenStore.get()) return;
    let alive = true;
    api
      .me()
      .then((u) => alive && (setMe(u), setStatus("authed")))
      .catch(() => alive && (setMe(null), setStatus("anon")));
    return () => {
      alive = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    tokenStore.set(access_token);
    const u = await api.me();
    setMe(u);
    setStatus("authed");
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ status, me, login, logout }),
    [status, me, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
