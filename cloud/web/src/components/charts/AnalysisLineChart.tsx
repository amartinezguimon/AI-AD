import { Line } from "react-chartjs-2";
import type { ChartOptions } from "chart.js";

interface Props {
  labels: string[];
  aTotal: (number | null)[];
  aLook: (number | null)[];
  bTotal: (number | null)[];
  bLook: (number | null)[];
  hideA0: boolean;
  hideA1: boolean;
  hideB0: boolean;
  hideB1: boolean;
  makeTitle: (idx: number) => string;
}

export default function AnalysisLineChart(p: Props) {
  const data = {
    labels: p.labels,
    datasets: [
      {
        label: "A · pasando",
        data: p.aTotal,
        borderColor: "#3d1a6e",
        backgroundColor: "rgba(61,26,110,.07)",
        borderWidth: 2.5,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: "#3d1a6e",
        tension: 0.35,
        fill: true,
        hidden: p.hideA0,
      },
      {
        label: "A · mirando",
        data: p.aLook,
        borderColor: "rgba(61,26,110,.4)",
        backgroundColor: "transparent",
        borderWidth: 1.5,
        pointRadius: 2,
        tension: 0.35,
        fill: false,
        hidden: p.hideA1,
      },
      {
        label: "B · pasando",
        data: p.bTotal,
        borderColor: "#E8394A",
        backgroundColor: "rgba(232,57,74,.07)",
        borderWidth: 2,
        borderDash: [6, 4],
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: "#E8394A",
        tension: 0.35,
        fill: true,
        hidden: p.hideB0,
      },
      {
        label: "B · mirando",
        data: p.bLook,
        borderColor: "rgba(232,57,74,.4)",
        backgroundColor: "transparent",
        borderWidth: 1.5,
        borderDash: [4, 3],
        pointRadius: 2,
        tension: 0.35,
        fill: false,
        hidden: p.hideB1,
      },
    ],
  };

  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#fff",
        titleColor: "#1C1C1C",
        bodyColor: "#666",
        borderColor: "#EBEBEB",
        borderWidth: 1,
        padding: 12,
        callbacks: {
          title: (items) => (items[0] ? p.makeTitle(items[0].dataIndex) : ""),
          label: (ctx) => " " + ctx.dataset.label + ": " + ctx.parsed.y,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { font: { size: 13, family: "Inter", weight: 800 }, color: "#3d1a6e", maxRotation: 0 },
      },
      y: {
        grid: { color: "#EBEBEB" },
        ticks: { font: { size: 12, family: "Inter", weight: 800 }, color: "#3d1a6e", maxTicksLimit: 6 },
        border: { display: false },
        min: 0,
      },
    },
  };

  return <Line data={data} options={options} />;
}
