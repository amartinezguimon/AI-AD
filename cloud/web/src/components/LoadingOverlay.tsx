// Full-screen loader, matching the mockup's "Cargando datos…" overlay.
export default function LoadingOverlay({ label = "Cargando datos…" }: { label?: string }) {
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-bg">
      <div className="flex flex-col items-center gap-3.5">
        <div className="spinner h-8 w-8 rounded-full border-[3px] border-gray5 border-t-purple" />
        <div className="text-[13px] font-semibold text-gray3">{label}</div>
      </div>
    </div>
  );
}
