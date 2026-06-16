import { useEffect, useMemo, useState } from "react";
import { useDashboardCtx } from "./DashboardLayout";
import AnalysisLineChart from "../components/charts/AnalysisLineChart";
import WeekdayChart from "../components/charts/WeekdayChart";
import RangeCalendar from "../components/RangeCalendar";
import { MONTHS, MONTHS_SHORT, WEEKDAYS_FULL, daysInMonth, fmtInt } from "../lib/format";
import {
  daysInRange,
  filterLook,
  fmtRange,
  getRangeStats,
  weekdayLabelsForRange,
  type Range,
} from "../lib/ranges";

type LookMode = "off" | "add" | "solo";
type AnalysisMode = "compare" | "weekday";
type CompareStep = "off" | "pickA" | "pickADone" | "pickB" | "pickBDone" | "done";

export default function AnalysisPage() {
  const { data } = useDashboardCtx();
  const { ensureMonth, getDaily } = data;

  const now = useMemo(() => new Date(), []);
  const curY = now.getFullYear();
  const curM0 = now.getMonth();
  const today = now.getDate();

  const [lookMode, setLookMode] = useState<LookMode>("off");
  const [secsFilter, setSecsFilter] = useState(2);
  const [compareMode, setCompareMode] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("compare");
  const [compareStep, setCompareStep] = useState<CompareStep>("off");
  const [rangeMode, setRangeMode] = useState<"A" | "B">("A");
  const [pendingStart, setPendingStart] = useState<number | null>(null);
  const [shortcut, setShortcut] = useState("");
  const [weekdayIndex, setWeekdayIndex] = useState(0);

  const [rangeA, setRangeA] = useState<Range | null>({
    year: curY, month0: curM0, start: Math.max(1, today - 6), end: today,
  });
  const [rangeB, setRangeB] = useState<Range | null>(null);
  const [anCalY, setAnCalY] = useState(curY);
  const [anCalM0, setAnCalM0] = useState(curM0);

  // Make sure every month referenced by the calendar or the ranges is loaded.
  useEffect(() => {
    ensureMonth(anCalY, anCalM0);
    if (rangeA) ensureMonth(rangeA.year, rangeA.month0);
    if (rangeB) ensureMonth(rangeB.year, rangeB.month0);
  }, [ensureMonth, anCalY, anCalM0, rangeA, rangeB]);

  const dailyA = rangeA ? getDaily(rangeA.year, rangeA.month0) : undefined;
  const dailyB = rangeB ? getDaily(rangeB.year, rangeB.month0) : undefined;

  const sA = useMemo(() => getRangeStats(rangeA, dailyA), [rangeA, dailyA]);
  const compareDone = compareMode && compareStep === "done";
  const sB = useMemo(
    () => (compareDone ? getRangeStats(rangeB, dailyB) : { total: [], look: [], labels: [] }),
    [compareDone, rangeB, dailyB],
  );

  // ── compare flow handlers ───────────────────────────────────────
  function toggleCompare() {
    if (compareMode) {
      setCompareMode(false);
      setCompareStep("off");
      setPendingStart(null);
    } else {
      setCompareMode(true);
      setCompareStep("pickA");
      setRangeMode("A");
      setPendingStart(null);
      setRangeB(null);
    }
  }

  function compareNext() {
    setCompareStep("pickB");
    setRangeMode("B");
    setPendingStart(null);
  }

  function compareConfirm() {
    setCompareStep("done");
  }

  function compareReset() {
    setCompareStep("pickA");
    setRangeMode("A");
    setPendingStart(null);
    setRangeA({ year: curY, month0: curM0, start: Math.max(1, today - 6), end: today });
    setRangeB(null);
  }

  function onCalClick(day: number) {
    if (analysisMode === "weekday") setAnalysisMode("compare");
    setShortcut("");
    const active = compareMode ? rangeMode : "A";

    if (pendingStart === null) {
      setPendingStart(day);
      const r: Range = { year: anCalY, month0: anCalM0, start: day, end: day };
      if (active === "A") setRangeA(r);
      else setRangeB(r);
      return;
    }
    const r: Range = {
      year: anCalY, month0: anCalM0,
      start: Math.min(pendingStart, day), end: Math.max(pendingStart, day),
    };
    if (active === "A") {
      setRangeA(r);
      if (compareMode) setCompareStep("pickADone");
    } else {
      setRangeB(r);
      if (compareMode) setCompareStep("pickBDone");
    }
    setPendingStart(null);
  }

  function onCalHover(day: number) {
    if (pendingStart === null) return;
    const active = compareMode ? rangeMode : "A";
    const r: Range = {
      year: anCalY, month0: anCalM0,
      start: Math.min(pendingStart, day), end: Math.max(pendingStart, day),
    };
    if (active === "A") setRangeA(r);
    else setRangeB(r);
  }

  function navCal(dir: number) {
    let m = anCalM0 + dir, y = anCalY;
    if (m > 11) { m = 0; y++; }
    if (m < 0) { m = 11; y--; }
    setAnCalM0(m);
    setAnCalY(y);
  }

  // ── shortcuts ───────────────────────────────────────────────────
  function applyShortcut(val: string) {
    setShortcut(val);
    if (val === "week") {
      const aStart = Math.max(1, today - 6);
      const bEnd = Math.max(1, aStart - 1);
      const bStart = Math.max(1, bEnd - 6);
      setAnalysisMode("compare");
      setRangeA({ year: curY, month0: curM0, start: aStart, end: today });
      setRangeB({ year: curY, month0: curM0, start: bStart, end: bEnd });
      enableCompareDone(curY, curM0);
    } else if (val === "month") {
      const [py, pm0] = curM0 === 0 ? [curY - 1, 11] : [curY, curM0 - 1];
      setAnalysisMode("compare");
      setRangeA({ year: curY, month0: curM0, start: 1, end: daysInMonth(curY, curM0) });
      setRangeB({ year: py, month0: pm0, start: 1, end: daysInMonth(py, pm0) });
      enableCompareDone(curY, curM0);
    } else if (val === "weekday") {
      setAnalysisMode("weekday");
      setWeekdayIndex(0);
    }
  }

  function enableCompareDone(y: number, m0: number) {
    setCompareMode(true);
    setCompareStep("done");
    setPendingStart(null);
    setAnCalY(y);
    setAnCalM0(m0);
  }

  // ── line-chart data (compare mode) ──────────────────────────────
  const maxLen = Math.max(sA.labels.length, sB.labels.length, 1);
  const pad = (arr: (number | null)[]) => [...arr, ...Array(maxLen - arr.length).fill(null)];
  const wdLabels = weekdayLabelsForRange(rangeA);
  const lineLabels = wdLabels || Array.from({ length: maxLen }, (_, i) => "Día " + (i + 1));
  const showLook = lookMode !== "off";
  const onlyLook = lookMode === "solo";

  const makeTitle = (idx: number) => {
    const dA = daysInRange(rangeA);
    const dB = compareMode ? daysInRange(rangeB) : [];
    const parts: string[] = [];
    if (rangeA && dA[idx] != null) parts.push(`A: ${dA[idx]} ${MONTHS_SHORT[rangeA.month0]}`);
    if (rangeB && dB[idx] != null) parts.push(`B: ${dB[idx]} ${MONTHS_SHORT[rangeB.month0]}`);
    return parts.join("   ·   ");
  };

  // ── weekday-mode data ───────────────────────────────────────────
  const weekday = useMemo(() => {
    const daily = getDaily(anCalY, anCalM0);
    const wdName = WEEKDAYS_FULL[weekdayIndex];
    if (!daily) return { wdName, labels: [] as string[], totals: [] as number[], looks: [] as number[] };
    const firstDow = new Date(anCalY, anCalM0, 1).getDay();
    const mondayIdx = firstDow === 0 ? 6 : firstDow - 1;
    const total = daysInMonth(anCalY, anCalM0);
    const days: number[] = [];
    for (let d = 1; d <= total; d++) {
      if ((mondayIdx + (d - 1)) % 7 === weekdayIndex && daily[String(d)]) days.push(d);
    }
    return {
      wdName,
      labels: days.map((d) => `${d} ${MONTHS_SHORT[anCalM0]}`),
      totals: days.map((d) => daily[String(d)].total),
      looks: days.map((d) => daily[String(d)].looking),
    };
  }, [getDaily, anCalY, anCalM0, weekdayIndex]);

  const showCardB = analysisMode === "weekday" || compareDone;
  const showB = compareMode && (compareStep === "pickB" || compareStep === "pickBDone" || compareStep === "done");

  return (
    <div className="flex flex-col" style={{ minHeight: "calc(100vh - 72px)" }}>
      <div className="mb-1 text-[18px] font-semibold text-dark">Análisis</div>
      <div className="mb-3.5 text-[11px] text-gray3">
        Selecciona un rango en el calendario · activa comparación para ver dos períodos
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[65fr_35fr] items-stretch gap-[14px]">
        {/* LEFT: chart */}
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-card bg-card p-6">
          <div className="mb-4 flex shrink-0 flex-wrap items-center justify-between gap-2">
            {analysisMode === "weekday" ? (
              <span className="text-[12px] font-semibold text-dark">
                Todos los {weekday.wdName.toLowerCase()}s · {MONTHS[anCalM0]} {anCalY}
              </span>
            ) : (
              <div className="flex flex-wrap items-center gap-3.5">
                <LegendLine color="var(--purple)">{fmtRange(rangeA) || "—"}</LegendLine>
                {compareDone && <LegendLine color="#E8394A">{fmtRange(rangeB) || "—"}</LegendLine>}
              </div>
            )}

            {analysisMode !== "weekday" && (
              <div className="flex items-center gap-2">
                <div className="flex gap-[2px] rounded-[20px] bg-gray6 p-[3px]">
                  <LookPill active={lookMode === "off"} onClick={() => setLookMode("off")}>Pasando</LookPill>
                  <LookPill active={lookMode === "add"} onClick={() => setLookMode("add")}>+ Mirando</LookPill>
                  <LookPill active={lookMode === "solo"} onClick={() => setLookMode("solo")}>Solo mirando</LookPill>
                </div>
                {showLook && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10.5px] text-gray3" title={secsFilter > 2 ? "Estimado (aún no medimos el tiempo exacto por persona)" : undefined}>
                      Mín.{secsFilter}s{secsFilter > 2 ? " ≈" : ""}
                    </span>
                    <input
                      type="range" min={1} max={15} value={secsFilter}
                      onChange={(e) => setSecsFilter(Number(e.target.value))}
                      className="w-[70px] cursor-pointer"
                    />
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="relative min-h-0 flex-1">
            {analysisMode === "weekday" ? (
              <WeekdayChart
                labels={weekday.labels}
                totals={weekday.totals}
                avgTotal={weekday.totals.length ? Math.round(weekday.totals.reduce((a, b) => a + b, 0) / weekday.totals.length) : 0}
              />
            ) : (
              <AnalysisLineChart
                labels={lineLabels}
                aTotal={pad(sA.total)}
                aLook={pad(filterLook(sA.look, secsFilter))}
                bTotal={compareMode ? pad(sB.total) : []}
                bLook={compareMode ? pad(filterLook(sB.look, secsFilter)) : []}
                hideA0={onlyLook}
                hideA1={!showLook}
                hideB0={!compareDone || onlyLook}
                hideB1={!compareDone || !showLook}
                makeTitle={makeTitle}
              />
            )}
          </div>
        </div>

        {/* RIGHT column */}
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
          <div className="shrink-0 rounded-card bg-card px-[18px] py-4">
            <RangeCalendar
              year={anCalY}
              month0={anCalM0}
              rangeA={rangeA}
              rangeB={rangeB}
              showB={showB}
              onPrev={() => navCal(-1)}
              onNext={() => navCal(1)}
              onClickDay={onCalClick}
              onHoverDay={onCalHover}
            />
          </div>

          {/* Compare panel */}
          <div className="shrink-0 rounded-card bg-card px-4 py-3.5">
            <div className="flex items-center justify-between">
              <span className="text-[11.5px] font-semibold text-dark">Comparar períodos</span>
              <button onClick={toggleCompare} className="cursor-pointer" aria-label="Activar comparación">
                <div
                  className="relative h-[18px] w-[34px] rounded-[9px] transition-colors"
                  style={{ background: compareMode ? "var(--purple)" : "var(--gray5)" }}
                >
                  <div
                    className="absolute top-0.5 h-3.5 w-3.5 rounded-full bg-white shadow transition-[left]"
                    style={{ left: compareMode ? 18 : 2 }}
                  />
                </div>
              </button>
            </div>

            <div className="mt-2.5">
              <select
                value={shortcut}
                onChange={(e) => applyShortcut(e.target.value)}
                className="w-full cursor-pointer rounded-lg border-[1.5px] border-gray5 bg-card px-2.5 py-[7px] text-[11.5px] text-dark outline-none"
              >
                <option value="">Atajos rápidos…</option>
                <option value="week">Esta semana vs anterior</option>
                <option value="month">Este mes vs anterior</option>
                <option value="weekday">Comparar días de la semana</option>
              </select>
            </div>

            {analysisMode === "weekday" && (
              <div className="mt-2">
                <div className="mb-1.5 text-center text-[10px] text-gray3">
                  ¿Qué día de la semana quieres comparar?
                </div>
                <div className="flex gap-[3px]">
                  {["L", "M", "X", "J", "V", "S", "D"].map((d, i) => (
                    <button
                      key={i}
                      onClick={() => setWeekdayIndex(i)}
                      className="flex-1 rounded-lg py-1.5 text-[11px] font-semibold transition-colors"
                      style={{
                        background: weekdayIndex === i ? "var(--purple)" : "var(--gray6)",
                        color: weekdayIndex === i ? "#fff" : "var(--gray3)",
                      }}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {compareMode && analysisMode !== "weekday" && (
              <CompareSteps
                step={compareStep}
                rangeA={rangeA}
                rangeB={rangeB}
                onNext={compareNext}
                onConfirm={compareConfirm}
                onReset={compareReset}
              />
            )}
          </div>

          {/* Stat card A */}
          <div className="flex min-h-0 flex-1 flex-col justify-evenly overflow-hidden rounded-card border-l-4 border-purple bg-card p-5">
            <div className="mb-2 text-[9.5px] font-semibold uppercase tracking-[0.07em] text-slate">
              {analysisMode === "weekday" ? `Media de los ${weekday.wdName.toLowerCase()}s` : fmtRange(rangeA) || "Período A"}
            </div>
            <div className="flex min-h-0 flex-1 items-center">
              {analysisMode === "weekday" ? <WeekdayStatsA wd={weekday} /> : <PeriodStats stats={sA} />}
            </div>
          </div>

          {/* Stat card B */}
          {showCardB && (
            <div className="flex min-h-0 flex-1 flex-col justify-evenly overflow-hidden rounded-card border-l-4 border-danger bg-card p-5">
              <div className="mb-2 text-[9.5px] font-semibold uppercase tracking-[0.07em] text-danger">
                {analysisMode === "weekday" ? `Mejor vs peor ${weekday.wdName.toLowerCase()}` : fmtRange(rangeB) || "Período B"}
              </div>
              <div className="flex min-h-0 flex-1 items-center">
                {analysisMode === "weekday" ? <WeekdayStatsB wd={weekday} /> : <PeriodStats stats={sB} />}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── small presentational pieces ───────────────────────────────────
function LegendLine({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-[7px]">
      <span className="h-[3px] w-5 rounded-[3px]" style={{ background: color }} />
      <span className="text-[12px] font-semibold" style={{ color }}>{children}</span>
    </div>
  );
}

function LookPill({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <div
      onClick={onClick}
      className="cursor-pointer rounded-[16px] px-2.5 py-1 text-[11px]"
      style={{
        background: active ? "var(--purple)" : "transparent",
        color: active ? "#fff" : "var(--gray3)",
        fontWeight: active ? 500 : 400,
      }}
    >
      {children}
    </div>
  );
}

function Divider() {
  return <div className="mx-1 w-px self-stretch bg-gray5" />;
}

function StatBlock({ value, label, sub }: { value: React.ReactNode; label: string; sub?: string }) {
  return (
    <div className="flex-1 px-0.5 py-1 text-center">
      <div className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.07em] text-slate">{label}</div>
      <div className="text-[28px] font-extrabold leading-none -tracking-[1px] text-dark">{value}</div>
      {sub && <div className="mt-[3px] text-[10px] text-gray3">{sub}</div>}
    </div>
  );
}

function PeriodStats({ stats }: { stats: { total: number[]; look: number[] } }) {
  const tot = stats.total.reduce((a, b) => a + b, 0);
  const lk = stats.look.reduce((a, b) => a + b, 0);
  const rate = tot ? Math.round((lk / tot) * 100) : 0;
  const avg = stats.total.length ? Math.round(tot / stats.total.length) : 0;
  return (
    <div className="flex w-full items-center">
      <StatBlock value={fmtInt(tot)} label="Total pasando" />
      <Divider />
      <StatBlock value={avg} label="Media diaria" />
      <Divider />
      <StatBlock value={`${rate}%`} label="Tasa" />
    </div>
  );
}

interface WeekdayData { wdName: string; labels: string[]; totals: number[]; looks: number[] }

function WeekdayStatsA({ wd }: { wd: WeekdayData }) {
  const avgTotal = wd.totals.length ? Math.round(wd.totals.reduce((a, b) => a + b, 0) / wd.totals.length) : 0;
  const avgLook = wd.looks.length ? Math.round(wd.looks.reduce((a, b) => a + b, 0) / wd.looks.length) : 0;
  return (
    <div className="flex w-full items-center">
      <StatBlock value={avgTotal} label="Pasando" />
      <Divider />
      <StatBlock value={avgLook} label="Mirando" />
    </div>
  );
}

function WeekdayStatsB({ wd }: { wd: WeekdayData }) {
  if (!wd.totals.length) {
    return <div className="w-full text-center text-[12px] text-gray3">Sin datos</div>;
  }
  const maxV = Math.max(...wd.totals), minV = Math.min(...wd.totals);
  const maxLabel = wd.labels[wd.totals.indexOf(maxV)];
  const minLabel = wd.labels[wd.totals.indexOf(minV)];
  return (
    <div className="flex w-full items-center">
      <StatBlock value={maxV} label="Mejor día" sub={maxLabel} />
      <Divider />
      <StatBlock value={minV} label="Peor día" sub={minLabel} />
    </div>
  );
}

function CompareSteps({
  step, rangeA, rangeB, onNext, onConfirm, onReset,
}: {
  step: CompareStep;
  rangeA: Range | null;
  rangeB: Range | null;
  onNext: () => void;
  onConfirm: () => void;
  onReset: () => void;
}) {
  const msg: Record<CompareStep, React.ReactNode> = {
    off: "",
    pickA: <><span className="text-purple">①</span> Selecciona el primer período</>,
    pickADone: <><span className="text-purple">①</span> Período seleccionado</>,
    pickB: <><span className="text-danger">②</span> Selecciona el segundo período</>,
    pickBDone: <><span className="text-danger">②</span> Período seleccionado</>,
    done: "✓ Comparando los dos períodos",
  };
  const aActive = true;
  const bActive = step === "pickB" || step === "pickBDone" || step === "done";

  return (
    <div className="mt-3">
      <div className="mb-2.5 text-center text-[11px] leading-snug text-gray2">{msg[step]}</div>
      <div className="mb-2.5 flex gap-2">
        <PeriodTag color="var(--purple)" active={aActive} title="Período A" label={fmtRange(rangeA) || "—"} />
        <PeriodTag color="#E8394A" active={bActive} title="Período B" label={fmtRange(rangeB) || "—"} />
      </div>
      <div>
        {step === "pickADone" && (
          <StepButton onClick={onNext} bg="var(--purple)">Siguiente →</StepButton>
        )}
        {step === "pickBDone" && (
          <StepButton onClick={onConfirm} bg="#22863A">Confirmar ✓</StepButton>
        )}
        {(step === "pickB" || step === "pickBDone" || step === "done") && (
          <button
            onClick={onReset}
            className="mt-1 w-full rounded-lg border-[1.5px] border-gray5 bg-transparent py-1.5 text-[11px] text-gray3"
          >
            ↺ Reiniciar
          </button>
        )}
      </div>
    </div>
  );
}

function PeriodTag({ color, active, title, label }: { color: string; active: boolean; title: string; label: string }) {
  return (
    <div
      className="flex-1 rounded-lg border-[1.5px] p-1.5 text-center text-[10.5px] font-semibold"
      style={{ borderColor: active ? color : "var(--gray5)", color: active ? color : "var(--gray4)", opacity: active ? 1 : 0.4 }}
    >
      <div className="mb-[1px] text-[9px] text-gray3">{title}</div>
      <div>{label}</div>
    </div>
  );
}

function StepButton({ onClick, bg, children }: { onClick: () => void; bg: string; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="mb-1 w-full rounded-lg py-2 text-[12px] font-semibold text-white"
      style={{ background: bg }}
    >
      {children}
    </button>
  );
}
