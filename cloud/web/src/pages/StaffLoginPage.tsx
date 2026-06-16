import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { useStaffAuth } from "../lib/staffAuth";

export default function StaffLoginPage() {
  const { login, status } = useStaffAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (status === "authed") navigate("/staff", { replace: true });
  }, [status, navigate]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      navigate("/staff", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "Correo o contraseña incorrectos."
          : "No se pudo iniciar sesión.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-dark px-6">
      <div className="w-full max-w-[380px]">
        <div className="mb-6 flex justify-center">
          <div className="rounded-[30px] bg-purple px-5 py-2 text-[15px] font-bold text-white">
            VisionMetrics <span className="font-normal opacity-70">· Admin</span>
          </div>
        </div>

        <form onSubmit={onSubmit} className="rounded-card bg-card p-7 shadow-sm">
          <h1 className="mb-1 text-[18px] font-bold text-dark">Back-office</h1>
          <p className="mb-5 text-[12px] text-gray3">Acceso del equipo VisionMetrics.</p>

          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate">
            Correo
          </label>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mb-4 w-full rounded-lg border border-gray5 px-3 py-2.5 text-[14px] outline-none focus:border-purple"
            placeholder="staff@visionmetrics.app"
          />

          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate">
            Contraseña
          </label>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mb-5 w-full rounded-lg border border-gray5 px-3 py-2.5 text-[14px] outline-none focus:border-purple"
            placeholder="••••••••"
          />

          {error && (
            <div className="mb-4 rounded-lg bg-danger/10 px-3 py-2 text-[12px] font-medium text-danger">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-purple py-2.5 text-[14px] font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
          >
            {busy ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
