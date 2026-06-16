import { Chart } from "react-chartjs-2";
import type { ChartData, ChartOptions } from "chart.js";
import { trafficColor } from "../../lib/format";

interface Props {
  days: number[];
  totals: number[];
  looks: number[];
  rates: number[];
  onSelectDay: (day: number) => void;
}

export default function MonthlyChart({ days, totals, looks, rates, onSelectDay }: Props) {
  const avgTot = totals.length ? Math.round(totals.reduce((a, b) => a + b, 0) / totals.length) : 0;
  const avgLook = looks.length ? Math.round(looks.reduce((a, b) => a + b, 0) / looks.length) : 0;

  const data = {
    labels: days.map(String),
    datasets: [
      {
        label: "Personas",
        data: totals,
        backgroundColor: totals.map((t) => trafficColor(t).bg),
        borderRadius: 5,
        borderSkipped: false,
        order: 2,
      },
      {
        type: "line",
        label: "Media pasando",
        data: days.map(() => avgTot),
        borderColor: "#1C1C1C",
        borderWidth: 1.5,
        borderDash: [4, 4],
        pointRadius: 0,
        fill: false,
        order: 1,
      },
      {
        type: "line",
        label: "Media mirando",
        data: days.map(() => avgLook),
        borderColor: "#F0DC6A",
        borderWidth: 1.5,
        borderDash: [4, 4],
        pointRadius: 0,
        fill: false,
        order: 0,
      },
    ],
  } as unknown as ChartData<"bar">;

  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    onClick: (_e, els) => {
      if (!els.length) return;
      const day = days[els[0].index];
      if (day != null) onSelectDay(day);
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        filter: (i) => i.datasetIndex === 0,
        callbacks: {
          title: (i) => "Día " + i[0].label,
          label: (i) => " " + i.raw + " personas",
          afterLabel: (i) => ` Miraron: ${looks[i.dataIndex]} (${rates[i.dataIndex]}%)`,
        },
        backgroundColor: "#fff",
        titleColor: "#1C1C1C",
        bodyColor: "#666",
        borderColor: "#EBEBEB",
        borderWidth: 1,
        padding: 10,
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          font: { size: 9, family: "Inter", weight: 700 },
          color: "#5e6e83",
          maxRotation: 0,
          maxTicksLimit: 15,
        },
      },
      y: {
        grid: { color: "#EBEBEB" },
        ticks: { font: { size: 10, family: "Inter", weight: 700 }, color: "#5e6e83", maxTicksLimit: 5 },
        border: { display: false },
        min: 0,
      },
    },
  };

  return <Chart type="bar" data={data} options={options} />;
}
