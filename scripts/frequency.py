#!/usr/bin/env python3
from pathlib import Path
import re
import csv
from collections import Counter, defaultdict
import matplotlib.pyplot as plt
import matplotlib as mpl

# ---------- Config ----------
summary_dir = Path("summary")
out_dir = Path("paper_data")
row_order = [
    "CNA Financial",
    "Change Healthcare",
    "Colonial Pipeline",
    "D.C. Metropolitan Police",
    "ExecuPharm",
    "Health Service Executive",
    "Kaseya VSA",
    "MGM Resorts",
    "Royal Mail",
]
header_angle_deg = 45
row_label_width_in = 0.0
cell_size_in = 0.34
dpi = 200

# Colors: 1 -> old 2, 2 -> mid(2,3), 3+ -> old 3
COLOR_2 = (0.86, 0.95, 0.86)
COLOR_3 = (0.32, 0.60, 0.32)
COLOR_1 = COLOR_2
COLOR_2_MID = tuple((a + b) / 2 for a, b in zip(COLOR_2, COLOR_3))

# ---------- Parse ----------
re_ta = re.compile(r"\bTA\d{4}\b")
re_t  = re.compile(r"\bT\d{4}\b")  # won't match TA####

def case_name(p: Path) -> str:
    base = p.stem
    for sep in (" - ", " – "):
        if sep in base:
            return base.split(sep, 1)[0]
    return base

def collect_counts():
    counts = defaultdict(Counter)
    all_ta, all_t = set(), set()
    for f in sorted(summary_dir.glob("*.txt")):
        name = case_name(f)
        txt = f.read_text(encoding="utf-8", errors="ignore")
        for code in re_ta.findall(txt):
            counts[name][code] += 1
            all_ta.add(code)
        for code in (c for c in re_t.findall(txt) if not c.startswith("TA")):
            counts[name][code] += 1
            all_t.add(code)
    return counts, sorted(all_ta), sorted(all_t)

# ---------- CSV ----------
def write_csv(rows, cols, counts, out_csv: Path):
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)

        # Header: codes + "Total"
        w.writerow(["Case"] + cols + ["Total"])

        # Body: each case + row total
        col_totals = [0] * len(cols)
        grand_total = 0

        for r in rows:
            c = counts.get(r, Counter())
            vals = [c.get(code, 0) for code in cols]
            row_total = sum(vals)
            w.writerow([r] + vals + [row_total])

            # accumulate column totals
            col_totals = [a + b for a, b in zip(col_totals, vals)]
            grand_total += row_total

        # Footer: TOTAL row (column sums + grand total)
        w.writerow(["TOTAL"] + col_totals + [grand_total])

# ---------- Renderer ----------
def save_table_png(title, rows, cols, counts, out_png: Path):
    # Build numeric + string data
    num_data, str_data, vmax = [], [], 0
    for r in rows:
        c = counts.get(r, Counter())
        vals = [c.get(code, 0) for code in cols]
        num_data.append(vals)
        str_data.append([("" if v == 0 else str(v)) for v in vals])
        vmax = max(vmax, *(v for v in vals))

    n_rows, n_cols = len(rows), len(cols)

    # Cell-squared sizing
    fig_w = max(4, row_label_width_in + n_cols * cell_size_in)
    fig_h = max(2.2, 0.9 * cell_size_in + n_rows * cell_size_in)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.axis("off")

    col_widths = [1.0 / max(1, n_cols)] * n_cols

    table = ax.table(
        cellText=str_data,
        rowLabels=rows,
        colLabels=cols,
        colWidths=col_widths,
        loc="center",
        cellLoc="center",
        rowLoc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.0, 1.12)

    # Minimal grid; header transparent; row labels right-justified
    for (ri, ci), cell in table.get_celld().items():
        cell.set_linewidth(0.3)
        cell.set_edgecolor((0, 0, 0, 0.25))

        if ri == 0:  # header row: no fill, no outline
            cell.set_facecolor((1, 1, 1, 0))
            cell.set_edgecolor((0, 0, 0, 0))
            txt = cell.get_text()
            txt.set_rotation(header_angle_deg)
            txt.set_ha("left")
            txt.set_va("bottom")

        if ci == -1 and ri >= 1:  # row labels
            cell.set_facecolor((1, 1, 1, 0))
            cell.set_linewidth(0.4)
            cell.set_edgecolor((0, 0, 0, 0.30))
            txt = cell.get_text()
            txt.set_ha("right")
            txt.set_va("center")
            txt.set_position((0.02, 0.5))

    # Discrete heatmap for data cells
    for (ri, ci), cell in table.get_celld().items():
        if ri >= 1 and ci >= 0:
            txt = cell.get_text().get_text()
            if txt == "":
                cell.set_facecolor((1, 1, 1, 1))
            else:
                v = int(txt)
                if v <= 0:
                    cell.set_facecolor((1, 1, 1, 1))
                elif v == 1:
                    cell.set_facecolor(COLOR_1)
                elif v == 2:
                    cell.set_facecolor(COLOR_2_MID)
                else:
                    cell.set_facecolor(COLOR_3)

    ax.set_title(title, pad=2, fontsize=11)
    plt.subplots_adjust(left=0.01, right=0.99, top=0.90, bottom=0.01)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)

# ---------- Histograms ----------
def save_hist_png_sorted_by_code(title, rows, cols, counts, out_png, include_zeros=True):
    """
    Sum counts across all cases for each code in cols, then plot a vertical bar chart.
    - Sorted by code label (lexicographic)
    - Bars colored with COLOR_2_MID
    - Y-axis is the count
    """
    # Totals per code (keep zeros if requested)
    totals = []
    for code in cols:
        s = sum(counts.get(r, Counter()).get(code, 0) for r in rows)
        if include_zeros or s > 0:
            totals.append((code, s))

    # Sort by code (tactic/tech label)
    totals.sort(key=lambda x: x[0])

    if not totals:
        print(f"[warn] No totals for {title}; skipping plot.")
        return

    labels, values = zip(*totals)
    n = len(values)

    # Dynamic sizing: widen with number of codes
    fig_w = max(6.5, 0.4 * n + 2.0)
    fig_h = 4.5

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=200)
    ax.bar(range(n), values, color=COLOR_2_MID)  # mid green
    ax.set_xticks(range(n), labels, rotation=60, ha="right")
    ax.set_ylabel("Count")
    ax.set_title(title, pad=6)

    # Light grid & value labels
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ymax = max(values) if values else 1
    for i, v in enumerate(values):
        ax.text(i, v + ymax*0.02, str(v), va="bottom", ha="center", fontsize=8)

    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)



# ---------- Run ----------
if __name__ == "__main__":
    counts, ta_cols, t_cols = collect_counts()

    # Paths
    out_dir.mkdir(parents=True, exist_ok=True)
    ta_png = out_dir / "TA_table.png"
    t_png  = out_dir / "T_table.png"
    ta_csv = out_dir / "TA_table.csv"
    t_csv  = out_dir / "T_table.csv"
    ta_hist_png = out_dir / "TA_hist.png"
    t_hist_png  = out_dir / "T_hist.png"


    # PNGs
    save_table_png("Figure 1: ATT&CK Tactics counts", row_order, ta_cols, counts, ta_png)
    save_table_png("Figure 2: ATT&CK Techniques counts", row_order, t_cols, counts, t_png)
    save_hist_png_sorted_by_code("Figure 3: ATT&CK Tactics frequency", row_order, ta_cols, counts, ta_hist_png)
    save_hist_png_sorted_by_code("Figure 4: ATT&CK Techniques frequency", row_order, t_cols, counts, t_hist_png)

    # CSVs
    write_csv(row_order, ta_cols, counts, ta_csv)
    write_csv(row_order, t_cols, counts, t_csv)

    print(f"Wrote: {ta_png}, {t_png}, {ta_csv}, {t_csv}")
