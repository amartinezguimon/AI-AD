import { Outlet } from "react-router-dom";
import { useStaffAuth } from "../lib/staffAuth";

export default function StaffLayout() {
  const { staff, logout } = useStaffAuth();
  return (
    <div className="min-h-screen px-8 pb-10 pt-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="rounded-[30px] bg-purple px-5 py-2 text-[15px] font-bold text-white">
          VisionMetrics <span className="font-normal opacity-70">· Admin</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[12px] text-gray2">{staff?.email}</span>
          <button
            onClick={logout}
            className="rounded-[30px] bg-card px-4 py-[7px] text-[13px] text-gray2 hover:bg-gray6"
          >
            Cerrar sesión
          </button>
        </div>
      </div>
      <Outlet />
    </div>
  );
}
