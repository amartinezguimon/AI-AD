import { MONTHS, WEEKDAY_LETTERS, daysInMonth, firstWeekdayOffset } from "../lib/format";
import { rangeHi, rangeLo, type Range } from "../lib/ranges";

interface Props {
  year: number;
  month0: number;
  rangeA: Range | null;
  rangeB: Range | null;
  showB: boolean;
  onPrev: () => void;
  onNext: () => void;
  onClickDay: (day: number) => void;
  onHoverDay: (day: number) => void;
}

const inThisMonth = (r: Range | null, y: number, m0: number) =>
  !!r && r.year === y && r.month0 === m0;

const lo = rangeLo;
const hi = rangeHi;

export default function RangeCalendar({
  year,
  month0,
  rangeA,
  rangeB,
  showB,
  onPrev,
  onNext,
  onClickDay,
  onHoverDay,
}: Props) {
  const offset = firstWeekdayOffset(year, month0);
  const total = daysInMonth(year, month0);

  const aHere = inThisMonth(rangeA, year, month0) ? rangeA! : null;
  const bHere = showB && inThisMonth(rangeB, year, month0) ? rangeB! : null;

  return (
    <div>
      <div className="mb-2.5 flex items-center justify-between">
        <div className="text-[12px] font-semibold text-dark">
          {MONTHS[month0]} {year}
        </div>
        <div className="flex gap-[5px]">
          <Nav onClick={onPrev}>‹</Nav>
          <Nav onClick={onNext}>›</Nav>
        </div>
      </div>

      <div className="mb-1.5 grid grid-cols-7 gap-[2px]">
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
          const inA = aHere ? d >= lo(aHere) && d <= hi(aHere) : false;
          const inB = bHere ? d >= lo(bHere) && d <= hi(bHere) : false;
          const isStartA = aHere ? d === lo(aHere) : false;
          const isEndA = aHere ? d === hi(aHere) : false;
          const isStartB = bHere ? d === lo(bHere) : false;
          const isEndB = bHere ? d === hi(bHere) : false;

          let circleBg = "transparent";
          let circleColor = "#555";
          let circleFw = 400;
          let circleShadow = "none";
          let cellBg = "transparent";

          if (isStartA || isEndA) {
            circleBg = "var(--purple)";
            circleColor = "#fff";
            circleFw = 700;
            circleShadow = "0 2px 6px rgba(61,26,110,.3)";
          } else if (isStartB || isEndB) {
            circleBg = "#E8394A";
            circleColor = "#fff";
            circleFw = 700;
          } else if (inA && inB) {
            cellBg = "rgba(61,26,110,.12)";
            circleColor = "var(--purple)";
            circleFw = 600;
          } else if (inA) {
            cellBg = "rgba(61,26,110,.1)";
            circleColor = "var(--purple)";
            circleFw = 600;
          } else if (inB) {
            cellBg = "rgba(232,57,74,.1)";
            circleColor = "#E8394A";
            circleFw = 600;
          }

          const isStart = isStartA || isStartB;
          const isEnd = isEndA || isEndB;
          let radius = "0";
          if (isStart && !isEnd) radius = "50% 0 0 50%";
          else if (isEnd && !isStart) radius = "0 50% 50% 0";
          else if (isStart && isEnd) radius = "50%";

          return (
            <div
              key={d}
              className="group flex cursor-pointer items-center justify-center py-0.5"
              style={{ background: cellBg, borderRadius: radius }}
              onClick={() => onClickDay(d)}
              onMouseEnter={() => onHoverDay(d)}
            >
              <div
                className="flex h-6 w-6 items-center justify-center rounded-full text-[10.5px] transition-transform duration-150 group-hover:scale-[1.2]"
                style={{ background: circleBg, color: circleColor, fontWeight: circleFw, boxShadow: circleShadow }}
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

function Nav({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="flex h-[26px] w-[26px] cursor-pointer items-center justify-center rounded-full bg-gray6 text-[13px] text-gray2 hover:bg-gray5"
    >
      {children}
    </div>
  );
}
