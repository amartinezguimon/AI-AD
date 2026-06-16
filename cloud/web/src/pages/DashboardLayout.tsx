import { useEffect, useMemo, useState } from "react";
import { Outlet, useOutletContext } from "react-router-dom";
import TopBar from "../components/TopBar";
import LoadingOverlay from "../components/LoadingOverlay";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useDashboard, type DashboardData } from "../hooks/useDashboard";
import type { Device, StoreInfo } from "../lib/types";

export interface DashboardCtx {
  data: DashboardData;
  store: StoreInfo | undefined;
  storeName: string;
}

export function useDashboardCtx() {
  return useOutletContext<DashboardCtx>();
}

export default function DashboardLayout() {
  const { me, logout } = useAuth();
  const [stores, setStores] = useState<StoreInfo[] | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [selectedStoreId, setSelectedStoreId] = useState<string>("");

  // Load the account's stores once. Default to the user's pinned store (store-
  // scoped user) or the first store (org-wide owner).
  useEffect(() => {
    api
      .stores()
      .then((s) => {
        setStores(s);
        setSelectedStoreId((cur) => cur || me?.store_id || s[0]?.id || "");
      })
      .catch(() => setStores([]));
  }, [me]);

  // Fleet status drives the "En directo" pill; refresh every 30s.
  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .devices()
        .then((d) => alive && setDevices(d))
        .catch(() => undefined);
    load();
    const t = setInterval(load, 30_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [selectedStoreId]);

  const data = useDashboard(selectedStoreId || undefined);

  const selectedStore = useMemo(
    () => stores?.find((s) => s.id === selectedStoreId),
    [stores, selectedStoreId],
  );
  const storeName = data.store?.name ?? selectedStore?.name ?? "tu tienda";

  const live = devices.some(
    (d) => (!selectedStoreId || d.store_id === selectedStoreId) && d.status === "online",
  );

  if (stores === null) return <LoadingOverlay />;
  if (stores.length === 0) return <NoStores onLogout={logout} email={me?.email} />;

  const ctx: DashboardCtx = { data, store: selectedStore, storeName };

  return (
    <div className="min-h-screen px-8 pb-10 pt-6">
      <TopBar
        stores={stores}
        selectedStoreId={selectedStoreId}
        onSelectStore={setSelectedStoreId}
        storeName={storeName}
        live={live}
        onLogout={logout}
      />
      <Outlet context={ctx} />
    </div>
  );
}

function NoStores({ onLogout, email }: { onLogout: () => void; email?: string }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center">
      <div className="text-[18px] font-bold text-dark">Tu cuenta aún no tiene tiendas</div>
      <p className="max-w-[420px] text-[13px] text-gray3">
        {email ? `Has entrado como ${email}. ` : ""}
        En cuanto VisionMetrics dé de alta tu tienda y conecte la cámara, verás aquí tus datos.
      </p>
      <button
        onClick={onLogout}
        className="mt-2 rounded-lg border border-gray5 px-4 py-2 text-[12px] text-gray2 hover:bg-gray6"
      >
        Cerrar sesión
      </button>
    </div>
  );
}
