import { MONTHS, WEEKDAY_LETTERS, daysInMonth, firstWeekdayOffset, trafficColor } from "../lib/format";
import type { DayStat } from "../lib/types";

interface Props {
  year: number;
  monthIndex0: number;
  selectedDay: number;
  todayDay: number | null; // set only when viewing the real current month
  daily: Record<string, DayStat> | undefined;
  onSelectDay: (day: number) => void;
  onPrev: () => void;
  onNext: () => void;
}

export default function MiniCalendar({
  year,
  monthIndex0,
  selectedDay,
  todayDay,
  daily,
  onSelectDay,
  onPrev,
  onNext,
}: Props) {
  const offset = firstWeekdayOffset(year, monthIndex0);
  const total = daysInMonth(year, monthIndex0);

  return (
    <div className="mb-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-[12px] font-semibold text-dark">
          {MONTHS[monthIndex0]} {year}
        </div>
        <div className="flex gap-[5px]">
          <CalNav onClick={onPrev}>‹</CalNav>
          <CalNav onClick={onNext}>›</CalNav>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-[2px]">
        {WEEKDAY_LETTERS.map((d, i) => (
          <div key={i} className="pb-0.5 text-center text-[9px] font-semibold text-[#bbb]">
            {d}
          </div>
        ))}
        {Array.from({ length: offset }).map((_, i) => (
          <div key={`pad-${i}`} />
        ))}
        {Array.from({ length: total }).map((_, idx) => {
          const d = idx + 1;
          const data = daily?.[String(d)];
          const isSel = d === selectedDay;
          const isToday = d === todayDay;
          const tc = data ? trafficColor(data.total) : { bg: "#EBEBEB", fg: "#bbb" };
          const bg = isSel ? "var(--purple)" : tc.bg;
          const color = isSel ? "#fff" : data ? (tc.fg === "#fff" ? "#fff" : "#333") : "#bbb";
          return (
            <div key={d} className="flex cursor-pointer items-center justify-center" onClick={() => onSelectDay(d)}>
              <div
                className="flex h-6 w-6 items-center justify-center rounded-full text-[10.5px] transition-transform duration-150 hover:scale-125"
                style={{
                  background: bg,
                  color,
                  fontWeight: isSel || isToday ? 700 : 500,
                  outline: isToday && !isSel ? "2.5px solid var(--purple)" : "none",
                  outlineOffset: "1px",
                  boxShadow: isSel ? "0 2px 8px rgba(61,26,110,.35)" : "none",
                }}
              >
                {d}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CalNav({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="flex h-[26px] w-[26px] cursor-pointer items-center justify-center rounded-full bg-gray6 text-[13px] text-gray2 hover:bg-gray5"
    >
      {children}
    </div>
  );
}
