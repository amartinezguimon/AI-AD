"""
Builds the business figures used in the executive report:
- tam_sam_som.png       (TAM/SAM/SOM funnel, EU primary)
- cashflow.png          (3-year cumulative cashflow, break-even)
- cost_breakdown.png    (3-year cost stack: personnel, infra, data, overhead)

Run:  python docs/figures/_build_business_figures.py

All assumptions live here as named constants so the report text and the
figure cannot drift apart.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIG_DIR = "docs/figures"
os.makedirs(FIG_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Bottom-up TAM/SAM/SOM — Spain primary, EU expansion
#
#   Physical retail enterprises in the EU distributive-trade sector
#   (Eurostat, retail is 57.1% of distributive trades = ~3.5M enterprises,
#   so ~3.5M × some-multi-store factor ≈ ~4.2M retail stores EU-wide —
#   we use a conservative 3.5M storefronts as addressable units).
#
#   Digital-signage adoption in retail ~23.8% (Persistence Mkt Research
#   cites retail as 23.8% revenue share of the 8.1B EU signage market
#   in 2025); we treat this as proxy for "stores with a display worth
#   measuring".  → SAM stores = 3.5M × 0.238.
#
#   SOM: 3-year realistic capture of 0.2% of SAM, weighted toward
#   Spain early.  Annual contract value (ACV) = €700 (€59/mo tier + setup).
# ─────────────────────────────────────────────────────────────

EU_RETAIL_STORES       = 3_500_000         # Eurostat distributive trades, conservative
SIGNAGE_PENETRATION_EU = 0.238             # EU digital-signage retail share (Persistence MR 2025)
SPAIN_RETAIL_STORES    = 450_000           # Spain INE (retail incl. food + non-food ~450k outlets)
SPAIN_SIGNAGE_PEN      = 0.18              # conservative: Spain below EU avg
ACV_EUR                = 1200              # blended: mix of €79/mo boutique, €59×multi-store, enterprise

tam_stores = EU_RETAIL_STORES * SIGNAGE_PENETRATION_EU
sam_stores = SPAIN_RETAIL_STORES * SPAIN_SIGNAGE_PEN + tam_stores * 0.10  # Spain + 10% EU adjacent
som_stores = 780                                                             # 3-yr realistic capture = end-of-Y3 paying stores (~0.5% of SAM)

tam_eur = tam_stores * ACV_EUR
sam_eur = sam_stores * ACV_EUR
som_eur = som_stores * ACV_EUR

# ── TAM / SAM / SOM funnel ────────────────────────────────
fig, ax = plt.subplots(figsize=(7.5, 4.5))
labels = ["TAM\nEU retail stores with signage",
          "SAM\nSpain + 10% EU addressable",
          "SOM\n3-yr realistic capture (0.2%)"]
vals_m = [tam_eur / 1e6, sam_eur / 1e6, som_eur / 1e6]
stores = [tam_stores, sam_stores, som_stores]
colors = ["#1f4e79", "#3a6fa5", "#6c9ccf"]

y = [2, 1, 0]
widths = [1.0, 0.65, 0.2]
for yi, w, c, lab, mv, st in zip(y, widths, colors, labels, vals_m, stores):
    ax.barh(yi, w, color=c, edgecolor="white")
    ax.text(w + 0.02, yi, f"{lab}\n{int(st):,} stores  →  €{mv:,.1f}M ACV",
            va="center", fontsize=9)
ax.set_xlim(0, 1.8); ax.set_ylim(-0.5, 2.5)
ax.set_yticks([]); ax.set_xticks([])
for spine in ("top", "right", "bottom", "left"):
    ax.spines[spine].set_visible(False)
ax.set_title("Market sizing — VisionMetrics AI (EU primary)")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/tam_sam_som.png", dpi=140); plt.close()

# ─────────────────────────────────────────────────────────────
# 3-year cumulative cashflow, break-even curve
# Assumptions (€ thousands):
#   Seed investment: 250
#   Year-1 cost:  2 FTE * 70k + infra 10k + onboarding 20k ≈ 170
#   Year-2 cost:  3 FTE * 75k + infra 20k + sales 40k ≈ 285
#   Year-3 cost:  5 FTE * 78k + infra 40k + sales 90k ≈ 520
#   Revenue ramp (stores paying at ACV 700 €/yr):
#     Y1 = 25 stores, Y2 = 180 stores, Y3 = 620 stores
# ─────────────────────────────────────────────────────────────
seed = 250
costs_k = [170, 285, 520]
stores_paying = [30, 220, 780]
rev_k = [s * ACV_EUR / 1000 for s in stores_paying]
net_k = [r - c for r, c in zip(rev_k, costs_k)]

quarters = np.arange(0, 13)  # Q0..Q12
# distribute yearly net linearly per quarter
per_q = []
for yr in range(3):
    for _ in range(4):
        per_q.append(net_k[yr] / 4)
cum = np.cumsum([-seed] + per_q)

fig, ax = plt.subplots(figsize=(7.5, 4.2))
ax.plot(quarters, cum, marker="o", color="#1f4e79", lw=2)
ax.axhline(0, color="#888", linestyle="--", lw=0.9)
break_q = next((q for q, v in zip(quarters, cum) if v >= 0), None)
if break_q is not None:
    ax.axvline(break_q, color="#2ca02c", linestyle=":", lw=1.2)
    ax.text(break_q + 0.1, cum.min() * 0.5,
            f"Break-even ≈ Q{break_q}", color="#2ca02c", fontsize=10)
ax.set_xticks(quarters)
ax.set_xticklabels([f"Q{q}" for q in quarters], fontsize=8)
ax.set_ylabel("cumulative cashflow (€k)")
ax.set_title("3-year cumulative cashflow — base case")
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/cashflow.png", dpi=140); plt.close()

# ─────────────────────────────────────────────────────────────
# 3-year cost breakdown stacked bar
# ─────────────────────────────────────────────────────────────
years = ["Year 1", "Year 2", "Year 3"]
personnel = [140, 225, 390]
infra     = [10, 20, 40]
sales     = [0, 20, 50]
data_ops  = [20, 20, 40]

fig, ax = plt.subplots(figsize=(6.5, 4.2))
bot = np.zeros(3)
for lab, vals, col in [("Personnel", personnel, "#1f4e79"),
                        ("Cloud & infra", infra, "#3a6fa5"),
                        ("Sales & marketing", sales, "#6c9ccf"),
                        ("Data / ops", data_ops, "#a9c7e6")]:
    ax.bar(years, vals, bottom=bot, label=lab, color=col)
    bot = bot + np.array(vals)
ax.set_ylabel("€ thousand")
ax.set_title("Projected cost structure (€k)")
ax.legend(frameon=False, loc="upper left", fontsize=9)
for i, total in enumerate(bot):
    ax.text(i, total + 10, f"€{int(total)}k", ha="center", fontsize=9)
ax.set_ylim(0, max(bot) * 1.18)
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/cost_breakdown.png", dpi=140); plt.close()

# Dump auditable numbers
with open(f"{FIG_DIR}/_assumptions.txt", "w", encoding="utf-8") as f:
    f.write("EXECUTIVE REPORT — QUANTITATIVE ASSUMPTIONS\n")
    f.write("===========================================\n\n")
    f.write(f"EU retail stores                    : {EU_RETAIL_STORES:>12,}\n")
    f.write(f"Signage penetration EU (retail)     : {SIGNAGE_PENETRATION_EU*100:>11.1f}%\n")
    f.write(f"Spain retail stores                 : {SPAIN_RETAIL_STORES:>12,}\n")
    f.write(f"Signage penetration Spain           : {SPAIN_SIGNAGE_PEN*100:>11.1f}%\n")
    f.write(f"Blended annual contract value (ACV) : €{ACV_EUR:>11}\n\n")
    f.write(f"TAM stores : {int(tam_stores):>12,}  →  €{tam_eur/1e6:,.1f}M ACV\n")
    f.write(f"SAM stores : {int(sam_stores):>12,}  →  €{sam_eur/1e6:,.1f}M ACV\n")
    f.write(f"SOM stores : {int(som_stores):>12,}  →  €{som_eur/1e6:,.1f}M ACV\n\n")
    f.write(f"Costs (€k)      Y1={costs_k[0]:>5}  Y2={costs_k[1]:>5}  Y3={costs_k[2]:>5}\n")
    f.write(f"Paying stores   Y1={stores_paying[0]:>5}  Y2={stores_paying[1]:>5}  Y3={stores_paying[2]:>5}\n")
    f.write(f"Revenue (€k)    Y1={rev_k[0]:>5.1f}  Y2={rev_k[1]:>5.1f}  Y3={rev_k[2]:>5.1f}\n")
    f.write(f"Net (€k)        Y1={net_k[0]:>5.1f}  Y2={net_k[1]:>5.1f}  Y3={net_k[2]:>5.1f}\n")

print("Business figures written to", FIG_DIR)
