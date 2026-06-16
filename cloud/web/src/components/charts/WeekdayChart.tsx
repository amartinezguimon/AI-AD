import { Chart } from "react-chartjs-2";
import type { ChartData, ChartOptions } from "chart.js";

interface Props {
  labels: string[];
  totals: number[];
  avgTotal: number;
}

export default function WeekdayChart({ labels, totals, avgTotal }: Props) {
  const data = {
    labels,
    datasets: [
      {
        label: "Personas pasando",
        data: totals,
        backgroundColor: "#3d1a6e",
        borderRadius: 6,
        borderSkipped: false,
        order: 2,
      },
      {
        type: "line",
        label: "Media",
        data: labels.map(() => avgTotal),
        borderColor: "#1C1C1C",
        borderWidth: 1.5,
        borderDash: [4, 4],
        pointRadius: 0,
        fill: false,
        order: 1,
      },
    ],
  } as unknown as ChartData<"bar">;

  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#fff",
        titleColor: "#1C1C1C",
        bodyColor: "#666",
        borderColor: "#EBEBEB",
        borderWidth: 1,
        padding: 10,
        filter: (i) => i.datasetIndex === 0,
        callbacks: { label: (ctx) => " " + ctx.parsed.y + " personas pasando" },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { font: { size: 13, family: "Inter", weight: 800 }, color: "#3d1a6e" },
      },
      y: {
        grid: { color: "#EBEBEB" },
        ticks: { font: { size: 12, family: "Inter", weight: 800 }, color: "#3d1a6e" },
        border: { display: false },
        min: 0,
      },
    },
  };

  return <Chart type="bar" data={data} options={options} />;
}
