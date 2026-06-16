import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "./lib/auth";
import { StaffAuthProvider, useStaffAuth } from "./lib/staffAuth";
import LoadingOverlay from "./components/LoadingOverlay";
import LoginPage from "./pages/LoginPage";
import DashboardLayout from "./pages/DashboardLayout";
import HomePage from "./pages/HomePage";
import AnalysisPage from "./pages/AnalysisPage";
import StaffLoginPage from "./pages/StaffLoginPage";
import StaffLayout from "./pages/StaffLayout";
import StaffOverviewPage from "./pages/StaffOverviewPage";
import type { ReactNode } from "react";

function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === "loading") return <LoadingOverlay label="Cargando…" />;
  if (status === "anon") return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireStaff({ children }: { children: ReactNode }) {
  const { status } = useStaffAuth();
  if (status === "loading") return <LoadingOverlay label="Cargando…" />;
  if (status === "anon") return <Navigate to="/staff/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { status } = useAuth();
  return (
    <Routes>
      {/* Client dashboard */}
      <Route
        path="/login"
        element={status === "authed" ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        element={
          <RequireAuth>
            <DashboardLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<HomePage />} />
        <Route path="/analysis" element={<AnalysisPage />} />
      </Route>

      {/* Platform staff back-office (separate auth) */}
      <Route
        path="/staff"
        element={
          <StaffAuthProvider>
            <Outlet />
          </StaffAuthProvider>
        }
      >
        <Route path="login" element={<StaffLoginPage />} />
        <Route
          element={
            <RequireStaff>
              <StaffLayout />
            </RequireStaff>
          }
        >
          <Route index element={<StaffOverviewPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
