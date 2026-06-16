import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { DayStat, HourBreakdown, StoreInfo } from "../lib/types";

interface MonthCache {
  daily?: Record<string, DayStat>;
  hourly?: Record<string, HourBreakdown>;
}

export interface DashboardData {
  store: StoreInfo | null;
  loading: boolean;
  error: string | null;
  /** Load a month if not already cached (no-op otherwise). monthIndex0 is 0..11. */
  ensureMonth: (year: number, monthIndex0: number) => void;
  getDaily: (year: number, monthIndex0: number) => Record<string, DayStat> | undefined;
  getHourly: (year: number, monthIndex0: number) => Record<string, HourBreakdown> | undefined;
}

const key = (year: number, m0: number) => `${year}-${m0}`;

/**
 * Per-store dashboard data with a month cache. One API call returns a month plus
 * its previous month, so a "this month vs last month" comparison costs one fetch.
 * Switching store clears the cache. Shared (via the layout) so Home and Analysis
 * reuse the same cached months.
 */
export function useDashboard(storeId: string | undefined): DashboardData {
  const [cache, setCache] = useState<Record<string, MonthCache>>({});
  const [store, setStore] = useState<StoreInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingCount, setLoadingCount] = useState(0);

  const cacheRef = useRef(cache);
  useEffect(() => {
    cacheRef.current = cache;
  }, [cache]);
  const inFlight = useRef<Set<string>>(new Set());

  // New store => forget the old store's data.
  useEffect(() => {
    setCache({});
    setStore(null);
    setError(null);
    inFlight.current.clear();
  }, [storeId]);

  const ensureMonth = useCallback(
    (year: number, m0: number) => {
      if (!storeId) return;
      const k = key(year, m0);
      if (cacheRef.current[k]?.daily || inFlight.current.has(k)) return;
      inFlight.current.add(k);
      setLoadingCount((c) => c + 1);
      api
        .dashboard({ storeId, year, month: m0 + 1 })
        .then((res) => {
          setStore(res.store);
          const [py, pm0] = m0 === 0 ? [year - 1, 11] : [year, m0 - 1];
          const prevK = key(py, pm0);
          setCache((prev) => ({
            ...prev,
            [k]: { daily: res.daily, hourly: res.hourly },
            // Seed the previous month's daily totals (free in the same response),
            // but never clobber hourly we may already hold for it.
            [prevK]: { daily: prev[prevK]?.daily ?? res.dailyPrev, hourly: prev[prevK]?.hourly },
          }));
        })
        .catch((e: unknown) =>
          setError(e instanceof Error ? e.message : "No se pudieron cargar los datos."),
        )
        .finally(() => {
          inFlight.current.delete(k);
          setLoadingCount((c) => c - 1);
        });
    },
    [storeId],
  );

  const getDaily = useCallback((year: number, m0: number) => cache[key(year, m0)]?.daily, [cache]);
  const getHourly = useCallback((year: number, m0: number) => cache[key(year, m0)]?.hourly, [cache]);

  return { store, loading: loadingCount > 0, error, ensureMonth, getDaily, getHourly };
}
