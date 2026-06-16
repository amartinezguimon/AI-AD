import { useCallback, useEffect, useState } from "react";
import { staffApi } from "../lib/staffApi";
import { timeAgo } from "../lib/format";
import type { AdminDevice, AdminOrg, AdminOverview, DeviceStatus } from "../lib/types";

export default function StaffOverviewPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [fleet, setFleet] = useState<AdminDevice[]>([]);
  const [orgs, setOrgs] = useState<AdminOrg[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const [ov, fl, og] = await Promise.all([
        staffApi.overview(),
        staffApi.fleet(),
        staffApi.orgs(),
      ]);
      setOverview(ov);
      setFleet(fl);
      setOrgs(og);
      setError(null);
      setUpdatedAt(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar.");
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <div className="text-[20px] font-semibold text-dark">Panel de control</div>
        <div className="text-[11px] text-gray3">
          {updatedAt ? `Actualizado ${timeAgo(updatedAt.toISOString())}` : "Cargando…"}
        </div>
      </div>
      <div className="mb-4 text-[12px] text-gray3">
        Estado de todas las tiendas y cámaras en tiempo real. Se actualiza solo cada 30&nbsp;s.
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-danger/10 px-3 py-2 text-[12px] font-medium text-danger">
          {error}
        </div>
      )}

      {/* Summary cards */}
      <div className="mb-5 grid grid-cols-3 gap-3 md:grid-cols-6">
        <SummaryCard label="Clientes" value={overview?.orgs} />
        <SummaryCard label="Tiendas" value={overview?.stores} />
        <SummaryCard label="Dispositivos" value={overview?.devices} />
        <SummaryCard label="En línea" value={overview?.online} tone="good" />
        <SummaryCard label="Sin conexión" value={overview?.offline} tone="bad" />
        <SummaryCard label="Sin estrenar" value={overview?.never_seen} tone="muted" />
      </div>

      {/* Fleet table */}
      <div className="mb-5 overflow-hidden rounded-card bg-card">
        <div className="border-b border-gray5 px-5 py-3.5 text-[13px] font-semibold text-dark">
          Flota de cámaras
        </div>
        {fleet.length === 0 ? (
          <div className="px-5 py-8 text-center text-[12px] text-gray3">
            Todavía no hay dispositivos dados de alta.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12.5px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-[0.06em] text-gray3">
                  <Th>Cliente</Th>
                  <Th>Tienda</Th>
                  <Th>Dispositivo</Th>
                  <Th>Estado</Th>
                  <Th>Cámara</Th>
                  <Th className="text-right">FPS</Th>
                  <Th className="text-right">Personas 24 h</Th>
                  <Th>Últimos datos</Th>
                  <Th>Versión</Th>
                  <Th>Última señal</Th>
                </tr>
              </thead>
              <tbody>
                {fleet.map((d) => (
                  <tr key={d.id} className="border-t border-gray6">
                    <Td className="font-semibold text-dark">{d.org_name}</Td>
                    <Td>{d.store_name}</Td>
                    <Td className="font-mono text-[11.5px] text-gray2">{d.id}</Td>
                    <Td><StatusBadge status={d.status} /></Td>
                    <Td><CameraCell ok={d.camera_ok} /></Td>
                    <Td className="text-right tabular-nums">
                      {d.fps_analysis != null ? d.fps_analysis.toFixed(1) : "—"}
                    </Td>
                    <Td className="text-right tabular-nums">
                      {d.recent_passersby != null ? d.recent_passersby.toLocaleString("es-ES") : "—"}
                    </Td>
                    <Td className={dataFresh(d.last_metric_at) ? "text-gray2" : "text-danger"}>
                      {timeAgo(d.last_metric_at)}
                    </Td>
                    <Td className="text-gray3">{d.agent_version ?? "—"}</Td>
                    <Td className="text-gray3">{timeAgo(d.last_seen_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Clients list */}
      <div className="overflow-hidden rounded-card bg-card">
        <div className="border-b border-gray5 px-5 py-3.5 text-[13px] font-semibold text-dark">
          Clientes
        </div>
        {orgs.length === 0 ? (
          <div className="px-5 py-8 text-center text-[12px] text-gray3">Sin clientes todavía.</div>
        ) : (
          <div className="divide-y divide-gray6">
            {orgs.map((o) => (
              <div key={o.id} className="flex items-center justify-between px-5 py-3">
                <div className="text-[13px] font-medium text-dark">{o.name}</div>
                <div className="text-[12px] text-gray3">
                  {o.store_count} {o.store_count === 1 ? "tienda" : "tiendas"} ·{" "}
                  {o.device_count} {o.device_count === 1 ? "cámara" : "cámaras"}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// A store is "fresh" if it produced metrics in the last ~2 hours.
function dataFresh(iso: string | null): boolean {
  if (!iso) return false;
  const t = new Date(iso).getTime();
  return !Number.isNaN(t) && Date.now() - t < 2 * 60 * 60 * 1000;
}

function SummaryCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: number | undefined;
  tone?: "default" | "good" | "bad" | "muted";
}) {
  const color =
    tone === "good" ? "#22863A" : tone === "bad" ? "#E8394A" : tone === "muted" ? "#999" : "#1C1C1C";
  return (
    <div className="rounded-card bg-card p-4">
      <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.07em] text-slate">
        {label}
      </div>
      <div className="text-[30px] font-extrabold leading-none -tracking-[1px]" style={{ color }}>
        {value ?? "—"}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: DeviceStatus }) {
  const map: Record<DeviceStatus, { label: string; bg: string; fg: string }> = {
    online: { label: "En línea", bg: "rgba(34,134,58,.12)", fg: "#22863A" },
    offline: { label: "Sin conexión", bg: "rgba(232,57,74,.12)", fg: "#E8394A" },
    provisioned: { label: "Sin estrenar", bg: "var(--gray6)", fg: "#999" },
  };
  const s = map[status];
  return (
    <span
      className="inline-block rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
      style={{ background: s.bg, color: s.fg }}
    >
      {s.label}
    </span>
  );
}

function CameraCell({ ok }: { ok: boolean | null }) {
  if (ok == null) return <span className="text-gray3">—</span>;
  return ok ? (
    <span className="font-semibold text-[#22863A]">OK</span>
  ) : (
    <span className="font-semibold text-danger">Fallo</span>
  );
}

function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <th className={`px-5 py-2.5 font-semibold ${className}`}>{children}</th>;
}

function Td({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-5 py-3 ${className}`}>{children}</td>;
}
