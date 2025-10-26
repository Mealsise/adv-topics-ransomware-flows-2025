#!/usr/bin/env python3
"""
clustering.py — incremental growth with realistic spacing and pull-only layout

Key features:
--------------
- Adds nodes one by one (start = most frequent; next = max total co-occurrence).
- Pull-only relaxation (spring-like attraction).
- Collision spacing: centers stay ≥ 2r apart (based on log frequency).
- Distance scale factor keeps graph open and readable.
- Produces both a static PNG and an animated GIF showing growth.

Outputs:
    paper_data/clustering_growth.png
    paper_data/clustering_growth.gif
    paper_data/growth_positions.json
"""

from pathlib import Path
import re, math, json
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import PillowWriter

# ---------- Config ----------
SUMMARY_DIR = Path("summary")
OUT_DIR = Path("paper_data")

MODE = "both"         # "T", "TA", or "both"
INCLUDE_CROSS = True
MIN_WEIGHT = 1

# Layout physics
RELAX_STEPS = 80
ATTRACTION  = 0.25
L_AT_W1     = 1.0
MIN_LEN     = 0.05
MAX_LEN     = 2.0
JITTER      = 0.02
TEMP_COOL   = 0.97
STEP_MAX    = 0.15

# Collision spacing
R_MIN = 0.05          # base collision radius
R_SCALE = 0.02        # scaling with log mentions
DIST_SCALE = 1.8      # global distance multiplier
COLLISION_PASSES = 2

# Visualization
MAKE_GIF = True
MAX_FRAMES = 250
DPI = 180
COLOR_TA = (0.86, 0.95, 0.86)
COLOR_T  = (0.32, 0.60, 0.32)

RE_TA = re.compile(r"\bTA\d{4}\b")
RE_T  = re.compile(r"\bT\d{4}\b")

# ---------- Parsing ----------
def parse_counts():
    cases, ta_counts, t_counts = [], [], []
    for f in sorted(SUMMARY_DIR.glob("*.txt")):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        ta, t = defaultdict(int), defaultdict(int)
        for c in RE_TA.findall(txt): ta[c]+=1
        for c in RE_T.findall(txt):
            if not c.startswith("TA"): t[c]+=1
        if ta or t:
            cases.append(f.stem)
            ta_counts.append(dict(ta))
            t_counts.append(dict(t))
    return cases, ta_counts, t_counts

def build_graph():
    cases, taC, tC = parse_counts()
    all_TA = sorted({c for d in taC for c in d})
    all_T  = sorted({c for d in tC  for c in d})
    if MODE=="TA": nodes = all_TA
    elif MODE=="T": nodes = all_T
    else: nodes = all_TA + all_T

    totals = {n:0 for n in nodes}
    for a,b in zip(taC,tC):
        for c,v in a.items():
            if c in totals: totals[c]+=v
        for c,v in b.items():
            if c in totals: totals[c]+=v

    edges = defaultdict(float)
    def add(a,b,w):
        if a==b or w<=0: return
        if a>b: a,b=b,a
        edges[(a,b)] += w

    for a,b in zip(taC,tC):
        if MODE in ("TA","both"):
            ks=list(a.keys())
            for i in range(len(ks)):
                for j in range(i+1,len(ks)):
                    add(ks[i], ks[j], a[ks[i]]*a[ks[j]])
        if MODE in ("T","both"):
            ks=list(b.keys())
            for i in range(len(ks)):
                for j in range(i+1,len(ks)):
                    add(ks[i], ks[j], b[ks[i]]*b[ks[j]])
        if MODE=="both" and INCLUDE_CROSS:
            for ka,va in a.items():
                for kb,vb in b.items():
                    add(ka,kb,va*vb)

    edges = {k:w for k,w in edges.items() if w>=MIN_WEIGHT}
    return nodes, totals, edges

def target_len(w):
    return DIST_SCALE * max(MIN_LEN, min(MAX_LEN, L_AT_W1 / max(1e-9, w)))

def node_radius(total_mentions: int) -> float:
    return R_MIN + R_SCALE * math.log1p(max(0, total_mentions))

# ---------- Layout ----------
def relax(P, edges, totals, steps=RELAX_STEPS, temp=1.0):
    """Pull-only springs + collision spacing (2r rule)."""
    nodes = list(P.keys())
    idx = {n:i for i,n in enumerate(nodes)}
    arr = np.array([P[n] for n in nodes], float)
    radii = np.array([node_radius(totals.get(n,0)) for n in nodes], float)

    for _ in range(steps):
        F = np.zeros_like(arr)
        # Springs
        for (a,b),w in edges.items():
            if a not in idx or b not in idx: continue
            i,j = idx[a], idx[b]
            v = arr[j]-arr[i]
            dist = np.linalg.norm(v)+1e-12
            u = v/dist
            f = ATTRACTION * (dist - target_len(w))
            F[i] += f*u
            F[j] -= f*u

        # Jitter
        F += np.random.normal(scale=JITTER*temp, size=F.shape)

        # Step + clamp
        step = np.clip(F, -STEP_MAX*temp, STEP_MAX*temp)
        arr += step

        # Collision spacing: ensure ≥ 2r
        for _ in range(COLLISION_PASSES):
            for i in range(len(nodes)):
                for j in range(i+1, len(nodes)):
                    delta = arr[j] - arr[i]
                    dist = np.linalg.norm(delta) + 1e-12
                    min_d = 2 * max(radii[i], radii[j])
                    if dist < min_d:
                        overlap = min_d - dist
                        dirv = delta / dist
                        arr[i] -= dirv * 0.5 * overlap
                        arr[j] += dirv * 0.5 * overlap

        temp *= TEMP_COOL

    for n,(x,y) in zip(nodes,arr):
        P[n] = np.array([x,y])
    return P

def incremental_layout(nodes, totals, edges):
    rng = np.random.default_rng(42)
    start = max(nodes, key=lambda n: totals.get(n,0))
    P = {start: np.zeros(2)}
    added = [start]
    remaining = [n for n in nodes if n != start]
    frames = []

    while remaining:
        best, bestscore = None, -1
        for n in remaining:
            score = sum(edges.get(tuple(sorted((n,m))),0.0) for m in added)
            if score > bestscore:
                best, bestscore = n, score
        if best is None: break
        remaining.remove(best)

        # Place near weighted centroid of connected nodes
        conn = [(m,edges.get(tuple(sorted((best,m))),0.0)) for m in added if (tuple(sorted((best,m))) in edges)]
        if conn:
            pts = np.array([P[m] for m,_ in conn], float)
            wts = np.array([w for _,w in conn], float)
            centroid = (pts * wts[:,None]).sum(axis=0) / max(1e-9, wts.sum())
            dist0 = 2 * node_radius(totals.get(best,0))
            angle = rng.uniform(0,2*math.pi)
            pos = centroid + dist0 * np.array([math.cos(angle), math.sin(angle)])
        else:
            pos = rng.normal(scale=1.0, size=2)

        P[best] = pos
        added.append(best)

        P = relax(P, edges, totals, steps=RELAX_STEPS)
        if MAKE_GIF:
            frames.append({n:P[n].copy() for n in P})
        if len(frames) >= MAX_FRAMES:
            break
    return P, frames


# ---------- Draw (ordered by weight) ----------
def draw_frame(P, edges, totals, outpath=None):
    nodes = list(P.keys())
    kinds = ["TA" if n.startswith("TA") else "T" for n in nodes]
    colors = [COLOR_TA if k=="TA" else COLOR_T for k in kinds]
    sizes = [180 for _ in nodes]

    fig, ax = plt.subplots(figsize=(9,7), dpi=DPI)
    ax.axis("off")

    if edges:
        # sort edges from weakest to strongest
        sorted_edges = sorted(edges.items(), key=lambda x: x[1])
        maxw = max(edges.values())
        for (a,b),w in sorted_edges:
            if a in P and b in P:
                xa,ya = P[a]; xb,yb = P[b]
                lw = 0.5 + 2.0 * math.sqrt(w/maxw)
                gray = 1.0 - 0.85 * math.sqrt(w/maxw)
                ax.plot([xa,xb],[ya,yb],
                        color=(gray,gray,gray,0.9),
                        lw=lw,
                        solid_capstyle="round")

    # draw nodes
    for n,(x,y),c in zip(nodes,[P[k] for k in nodes],colors):
        ax.scatter(x,y,s=sizes[nodes.index(n)],
                   c=[c],edgecolors=(0,0,0,0.35),linewidths=0.6)
    # draw labels
    for n,(x,y) in P.items():
        ax.text(x,y,n,fontsize=7,ha="center",va="center")

    plt.tight_layout()
    if outpath:
        plt.savefig(outpath,bbox_inches="tight",pad_inches=0.02)
    plt.close(fig)


def make_gif(frames, edges, totals, out_gif):
    writer = PillowWriter(fps=10)
    fig, ax = plt.subplots(figsize=(9,7), dpi=DPI)
    with writer.saving(fig, str(out_gif), 100):
        maxw = max(edges.values()) if edges else 1.0
        sorted_edges = sorted(edges.items(), key=lambda x: x[1])
        for frame in frames:
            ax.clear(); ax.axis("off")
            P = frame
            nodes = list(P.keys())
            kinds = ["TA" if n.startswith("TA") else "T" for n in nodes]
            color_map = {"TA": COLOR_TA, "T": COLOR_T}

            # edges: weak → strong
            for (a,b),w in sorted_edges:
                if a in P and b in P:
                    xa,ya = P[a]; xb,yb = P[b]
                    lw = 0.5 + 2.0 * math.sqrt(w/maxw)
                    gray = 1.0 - 0.85 * math.sqrt(w/maxw)
                    ax.plot([xa,xb],[ya,yb],
                            color=(gray,gray,gray,0.9),
                            lw=lw,
                            solid_capstyle="round")

            # nodes then labels
            for n,(x,y) in P.items():
                ax.scatter(x,y,s=180,
                           c=[color_map["TA" if n.startswith("TA") else "T"]],
                           edgecolors=(0,0,0,0.35),
                           linewidths=0.6)
            for n,(x,y) in P.items():
                ax.text(x,y,n,fontsize=7,ha="center",va="center")
            writer.grab_frame()
    plt.close(fig)



# ---------- Main ----------
def main():
    nodes, totals, edges = build_graph()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    P, frames = incremental_layout(nodes, totals, edges)
    P = relax(P, edges, totals, steps=RELAX_STEPS*2)

    draw_frame(P, edges, totals, OUT_DIR/"clustering_growth.png")
    if MAKE_GIF and frames:
        make_gif(frames, edges, totals, OUT_DIR/"clustering_growth.gif")
    with (OUT_DIR/"growth_positions.json").open("w", encoding="utf-8") as f:
        json.dump({n: [float(P[n][0]), float(P[n][1])] for n in P}, f, indent=2)
    print("Saved:", OUT_DIR/"clustering_growth.png", OUT_DIR/"clustering_growth.gif", OUT_DIR/"growth_positions.json")

if __name__ == "__main__":
    main()
