// Wire types — mirror the cloud API's pydantic schemas (cloud/app/schemas.py).

/** One day's summary, in plain business terms. */
export interface DayStat {
  total: number; // passersby (foot traffic)
  looking: number; // engaged (looked over the threshold)
  rate: number; // looking / total * 100, whole %
  avg: number; // mean seconds an engaged person looked
}

/** Per-hour counts for one day; indices 0..11 == 9h..20h. */
export interface HourBreakdown {
  passing: number[];
  looking: number[];
}

export interface StoreInfo {
  id: string;
  name: string;
  address: string | null;
  timezone: string;
}

/** Response of GET /v1/dashboard?store_id&year&month. Maps are keyed by day-of-month. */
export interface DashboardData {
  store: StoreInfo;
  year: number;
  month: number; // 1..12
  has_data: boolean;
  daily: Record<string, DayStat>;
  dailyPrev: Record<string, DayStat>;
  hourly: Record<string, HourBreakdown>;
}

export interface Me {
  id: string;
  email: string;
  role: "admin" | "viewer";
  org_id: string;
  store_id: string | null;
}

export type DeviceStatus = "provisioned" | "online" | "offline";

export interface Device {
  id: string;
  store_id: string;
  status: DeviceStatus;
  agent_version: string | null;
  last_seen_at: string | null;
}

// ── platform staff (back-office) ──────────────────────────────────
export interface StaffMe {
  id: string;
  email: string;
}

export interface AdminOverview {
  orgs: number;
  stores: number;
  devices: number;
  online: number;
  offline: number;
  never_seen: number;
}

export interface AdminDevice {
  id: string;
  org_id: string;
  org_name: string;
  store_id: string;
  store_name: string;
  status: DeviceStatus;
  agent_version: string | null;
  last_seen_at: string | null;
  camera_ok: boolean | null;
  fps_analysis: number | null;
  people_tracked: number | null;
  last_metric_at: string | null;
  recent_passersby: number | null;
}

export interface AdminOrg {
  id: string;
  name: string;
  created_at: string;
  store_count: number;
  device_count: number;
}
