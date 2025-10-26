from pathlib import Path
import re
import csv
import math
import numpy as np
import matplotlib.pyplot as plt

# ---------- Config ----------
SUMMARY_DIR = Path("summary")
OUT_DIR = Path("paper_data")
PNG_PATH = OUT_DIR / "weighted_cosine_TxT.png"
CSV_PATH = OUT_DIR / "weighted_cosine_TxT.csv"
DPI = 200
LABEL_ROT = 65
ANNOT_THRESH = 0.30  # annotate cells >= this score

RE_T = re.compile(r"\bT\d{4}\b")  # techniques only (won't match TA####)


def case_name(p: Path) -> str:
    base = p.stem
    for sep in (" - ", " – "):
        if sep in base:
            return base.split(sep, 1)[0]
    return base


def load_counts_matrix():
    """Return (codes, X) where X is (n_cases x n_codes) counts per campaign."""
    case_counters = []
    for f in sorted(SUMMARY_DIR.glob("*.txt")):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        codes = [c for c in RE_T.findall(txt) if not c.startswith("TA")]
        if not codes:
            continue
        cnt = {}
        for c in codes:
            cnt[c] = cnt.get(c, 0) + 1
        case_counters.append(cnt)

    codes = sorted({c for cnt in case_counters for c in cnt})
    if not codes:
        raise SystemExit("[warn] No T#### codes found; nothing to plot.")

    code_idx = {c: j for j, c in enumerate(codes)}
    X = np.zeros((len(case_counters), len(codes)), dtype=float)
    for i, cnt in enumerate(case_counters):
        for c, v in cnt.items():
            X[i, code_idx[c]] = float(v)
    return codes, X


def compute_weighted_cosine(codes, X):
    """Compute symmetric weighted cosine similarity matrix."""
    # Weighted co-occurrence
    co = X.T @ X  # (n_codes x n_codes), sum count(A)*count(B) across campaigns

    # Totals per code
    total = X.sum(axis=0)  # (n_codes,)
    denom = np.sqrt(np.outer(total, total))  # √(total(A)*total(B))

    # Safe divide
    with np.errstate(divide="ignore", invalid="ignore"):
        sim = np.divide(co, denom, out=np.zeros_like(co, dtype=float), where=(denom > 0))

    # Self-similarity isn't informative here
    np.fill_diagonal(sim, 0.0)
    return sim


def save_csv(codes, M, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([""] + codes)
        for i, a in enumerate(codes):
            w.writerow([a] + [f"{M[i, j]:.6f}" for j in range(len(codes))])


def plot_heatmap(codes, M, path: Path):
    n = len(codes)
    # Figure size scales with matrix size
    fig_w = max(6.5, 0.25 * n + 3.0)
    fig_h = max(4.2, 0.25 * n + 2.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)

    # Mask zeros -> white, Reds for >0
    mask = (M <= 0)
    data = np.ma.array(M, mask=mask)

    cmap = plt.cm.Reds
    cmap.set_bad(color="white")
    vmax = float(M.max()) if M.size else 1.0
    if vmax == 0:
        vmax = 1.0

    im = ax.imshow(data, aspect="auto", cmap=cmap, vmin=0.0, vmax=vmax)

    # Labels
    ax.set_xticks(range(n))
    ax.set_xticklabels(codes, rotation=LABEL_ROT, ha="right", fontsize=7)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position('top')

    ax.set_yticks(range(n))
    ax.set_yticklabels(codes, fontsize=7)

    ax.set_xlabel("Technique B (top)")
    ax.set_ylabel("Technique A (left)")
    ax.set_title("Technique Co-occurrence Similarity (Weighted Cosine)", pad=6)

    # Annotate notable cells
    for i in range(n):
        for j in range(n):
            v = M[i, j]
            if v >= ANNOT_THRESH:
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6)

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.015)
    cbar.set_label("Similarity", rotation=270, labelpad=10)

    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def main():
    codes, X = load_counts_matrix()
    M = compute_weighted_cosine(codes, X)
    save_csv(codes, M, CSV_PATH)
    plot_heatmap(codes, M, PNG_PATH)
    print(f"Wrote: {PNG_PATH} and {CSV_PATH}")


if __name__ == "__main__":
    main()
