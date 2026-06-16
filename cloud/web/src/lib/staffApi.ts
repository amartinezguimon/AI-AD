// API client for the platform back-office (us). Kept separate from the client
// dashboard's api.ts on purpose: a different token type (staff JWT, stored under
// its own key) and a different 401 target (/staff/login). Same relative `/v1`.

import type { AdminDevice, AdminOrg, AdminOverview, StaffMe } from "./types";
import { ApiError } from "./api";

const STAFF_TOKEN_KEY = "vm_staff_token";

export const staffTokenStore = {
  get: (): string | null => localStorage.getItem(STAFF_TOKEN_KEY),
  set: (t: string) => localStorage.setItem(STAFF_TOKEN_KEY, t),
  clear: () => localStorage.removeItem(STAFF_TOKEN_KEY),
};

let onStaffUnauthorized: (() => void) | null = null;
export function setStaffUnauthorizedHandler(fn: (() => void) | null) {
  onStaffUnauthorized = fn;
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = staffTokenStore.get();
  const headers = new Headers(opts.headers);
  headers.set("Accept", "application/json");
  if (opts.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`/v1${path}`, { ...opts, headers });

  if (res.status === 401) {
    staffTokenStore.clear();
    onStaffUnauthorized?.();
    throw new ApiError(401, "Tu sesión de administrador ha caducado.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const staffApi = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/staff/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<StaffMe>("/admin/me"),
  overview: () => request<AdminOverview>("/admin/overview"),
  orgs: () => request<AdminOrg[]>("/admin/orgs"),
  fleet: () => request<AdminDevice[]>("/admin/fleet"),
};
