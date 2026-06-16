// Single integration point with the cloud API.
//
// All calls use RELATIVE URLs under `/v1`. In dev, Vite proxies that to the local
// backend; in production Caddy serves this build and proxies `/v1` to the API on
// the same origin. So the code never hardcodes a host and works in both places.

import type { DashboardData, Device, Me, StoreInfo } from "./types";

const TOKEN_KEY = "vm_token";

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

// The auth layer registers a callback so a 401 anywhere kicks the user to /login.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = tokenStore.get();
  const headers = new Headers(opts.headers);
  headers.set("Accept", "application/json");
  if (opts.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`/v1${path}`, { ...opts, headers });

  if (res.status === 401) {
    tokenStore.clear();
    onUnauthorized?.();
    throw new ApiError(401, "Tu sesión ha caducado. Inicia sesión de nuevo.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function qs(params: Record<string, string | number | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<Me>("/me"),

  stores: () => request<StoreInfo[]>("/stores"),

  devices: () => request<Device[]>("/devices"),

  dashboard: (opts: { storeId?: string; year?: number; month?: number }) =>
    request<DashboardData>(
      `/dashboard${qs({ store_id: opts.storeId, year: opts.year, month: opts.month })}`,
    ),
};
