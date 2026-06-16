import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { setStaffUnauthorizedHandler, staffApi, staffTokenStore } from "./staffApi";
import type { StaffMe } from "./types";

type Status = "loading" | "authed" | "anon";

interface StaffAuthValue {
  status: Status;
  staff: StaffMe | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const StaffAuthContext = createContext<StaffAuthValue | null>(null);

export function StaffAuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>(staffTokenStore.get() ? "loading" : "anon");
  const [staff, setStaff] = useState<StaffMe | null>(null);

  const logout = useCallback(() => {
    staffTokenStore.clear();
    setStaff(null);
    setStatus("anon");
  }, []);

  useEffect(() => {
    setStaffUnauthorizedHandler(() => {
      setStaff(null);
      setStatus("anon");
    });
    return () => setStaffUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    if (!staffTokenStore.get()) return;
    let alive = true;
    staffApi
      .me()
      .then((s) => alive && (setStaff(s), setStatus("authed")))
      .catch(() => alive && (setStaff(null), setStatus("anon")));
    return () => {
      alive = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await staffApi.login(email, password);
    staffTokenStore.set(access_token);
    const s = await staffApi.me();
    setStaff(s);
    setStatus("authed");
  }, []);

  const value = useMemo<StaffAuthValue>(
    () => ({ status, staff, login, logout }),
    [status, staff, login, logout],
  );

  return <StaffAuthContext.Provider value={value}>{children}</StaffAuthContext.Provider>;
}

export function useStaffAuth(): StaffAuthValue {
  const ctx = useContext(StaffAuthContext);
  if (!ctx) throw new Error("useStaffAuth must be used inside <StaffAuthProvider>");
  return ctx;
}
