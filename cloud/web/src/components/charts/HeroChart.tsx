import { Bar } from "react-chartjs-2";
import type { Chart as ChartJSInstance, ChartOptions, Plugin } from "chart.js";

const HOUR_LABELS = ["9h", "10h", "11h", "12h", "13h", "14h", "15h", "16h", "17h", "18h", "19h", "20h"];

// Highlight the busiest hour with deeper colours (same as the mockup's peakCols).
function peakColors(passing: number[], dk: string, lt: string, pkDk: string, pkLt: string) {
  const peak = passing.indexOf(Math.max(...passing, 0));
  return {
    dark: passing.map((_, i) => (i === peak ? pkDk : dk)),
    light: passing.map((_, i) => (i === peak ? pkLt : lt)),
  };
}

function niceCeil(max: number): number {
  if (max <= 0) return 10;
  return Math.ceil(max / 10) * 10;
}

// Draws the total (passing) above each bar — Hector's lookingLabels plugin.
const totalLabels: Plugin<"bar"> = {
  id: "totalLabels",
  afterDatasetsDraw(chart: ChartJSInstance) {
    const ds0 = chart.data.datasets[0];
    const ds1 = chart.data.datasets[1];
    if (!ds0 || !ds1) return;
    const meta1 = chart.getDatasetMeta(1);
    const ctx = chart.ctx;
    ctx.save();
    ctx.font = "700 11px Inter, system-ui, sans-serif";
    ctx.fillStyle = "rgba(94,110,131,0.85)";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    meta1.data.forEach((bar, i) => {
      const total = (Number(ds0.data[i]) || 0) + (Number(ds1.data[i]) || 0);
      if (total <= 0) return;
      ctx.fillText(String(total), bar.x, bar.y - 4);
    });
    ctx.restore();
  },
};

export default function HeroChart({ passing, looking }: { passing: number[]; looking: number[] }) {
  const onlyPassing = passing.map((t, i) => Math.max(0, t - (looking[i] ?? 0)));
  const cols = peakColors(passing, "#3d1a6e", "#D8D8D8", "#1a0a3e", "#c9b8e8");
  const yMax = niceCeil(Math.max(...passing, 0));

  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        mode: "index",
        backgroundColor: "#fff",
        titleColor: "#1C1C1C",
        bodyColor: "#666",
        borderColor: "#EBEBEB",
        borderWidth: 1,
        padding: 12,
        callbacks: {
          afterBody: (items) => {
            const t = items.reduce((s, i) => s + (i.parsed.y ?? 0), 0);
            const l = items.find((i) => i.dataset.label === "Miraron +2s");
            return l && t ? ["Tasa: " + Math.round(((l.parsed.y ?? 0) / t) * 100) + "%"] : [];
          },
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        grid: { display: false },
        ticks: { font: { size: 13, family: "Inter", weight: 800 }, color: "#3d1a6e", maxTicksLimit: 12 },
      },
      y: {
        stacked: true,
        min: 0,
        max: yMax,
        grid: { color: "#EBEBEB" },
        ticks: { font: { size: 12, family: "Inter", weight: 800 }, color: "#3d1a6e", maxTicksLimit: 6 },
        border: { display: false },
      },
    },
  };

  const data = {
    labels: HOUR_LABELS,
    datasets: [
      {
        label: "Miraron +2s",
        data: looking,
        backgroundColor: cols.dark,
        borderRadius: { topLeft: 0, topRight: 0, bottomLeft: 7, bottomRight: 7 },
        borderSkipped: false,
        stack: "s",
      },
      {
        label: "Solo pasaron",
        data: onlyPassing,
        backgroundColor: cols.light,
        borderRadius: { topLeft: 7, topRight: 7, bottomLeft: 0, bottomRight: 0 },
        borderSkipped: false,
        stack: "s",
      },
    ],
  };

  return <Bar data={data} options={options} plugins={[totalLabels]} />;
}
