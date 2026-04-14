"""
Advanced gaze analysis module
Supports:
- Heatmaps
- Multiple AOIs
- AOI-labeled fixation detection
- Fixation visualization maps
"""

from __future__ import annotations
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Tuple, Optional, List, Dict
from datetime import datetime


# ======================================================
# Utility
# ======================================================

def ensure_analysis_dir():
    if not os.path.exists("analysis"):
        os.makedirs("analysis")
    return "analysis"


def normalize_coordinates(coords):
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return min(xs), min(ys), max(xs), max(ys)


def point_in_area(x, y, area):
    min_x, min_y, max_x, max_y = area
    return min_x <= x <= max_x and min_y <= y <= max_y


# ======================================================
# Heatmap
# ======================================================

def compute_heatmap(csv_file, grid_size=(50, 50)):
    df = pd.read_csv(csv_file)

    plt.figure(figsize=(12, 6))
    sns.kdeplot(
        x=df["x"],
        y=df["y"],
        fill=True,
        cmap="rocket",
        thresh=0,
        levels=100
    )
    plt.gca().invert_yaxis()
    plt.title("Gaze Heatmap")

    analysis_dir = ensure_analysis_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(analysis_dir, f"heatmap_{ts}.png")

    plt.savefig(out, dpi=150)
    plt.show()
    print(f"Heatmap saved → {out}")


# ======================================================
# Fixations with multiple AOIs
# ======================================================

def compute_fixations_multi_aoi(
    csv_file: str,
    aois: Dict[str, Tuple[float, float, float, float]],
    fixation_threshold: float = 0.5
):
    df = pd.read_csv(csv_file)

    results = []
    fixation_id = 1

    for aoi_name, area in aois.items():
        df["in_aoi"] = df.apply(
            lambda r: point_in_area(r["x"], r["y"], area), axis=1
        )

        in_fix = False
        start_time = None
        start_idx = None

        for idx, row in df.iterrows():
            if row["in_aoi"]:
                if not in_fix:
                    in_fix = True
                    start_time = row["timestamp"]
                    start_idx = idx
            else:
                if in_fix:
                    duration = row["timestamp"] - start_time
                    if duration >= fixation_threshold:
                        chunk = df.loc[start_idx:idx - 1]
                        results.append({
                            "fixation_id": fixation_id,
                            "AOI": aoi_name,
                            "start_time": start_time,
                            "end_time": row["timestamp"],
                            "duration": duration,
                            "mean_x": chunk["x"].mean(),
                            "mean_y": chunk["y"].mean(),
                            "num_points": len(chunk)
                        })
                        fixation_id += 1
                    in_fix = False

        if in_fix:
            last_time = df.iloc[-1]["timestamp"]
            duration = last_time - start_time
            if duration >= fixation_threshold:
                chunk = df.loc[start_idx:]
                results.append({
                    "fixation_id": fixation_id,
                    "AOI": aoi_name,
                    "start_time": start_time,
                    "end_time": last_time,
                    "duration": duration,
                    "mean_x": chunk["x"].mean(),
                    "mean_y": chunk["y"].mean(),
                    "num_points": len(chunk)
                })
                fixation_id += 1

    df_fix = pd.DataFrame(results)

    analysis_dir = ensure_analysis_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(analysis_dir, f"fixations_{ts}.csv")
    df_fix.to_csv(out, index=False)

    print(f"\nFixations saved → {out}")
    print(df_fix.groupby("AOI")["duration"].sum())

    return df_fix


# ======================================================
# Visualization
# ======================================================

def plot_fixation_map(csv_file, aois, fix_df):
    df = pd.read_csv(csv_file)

    plt.figure(figsize=(10, 7))

    plt.plot(df["x"], df["y"], alpha=0.3)
    plt.scatter(df["x"], df["y"], s=5, alpha=0.3)

    # Draw AOIs
    for name, area in aois.items():
        min_x, min_y, max_x, max_y = area
        rect = plt.Rectangle(
            (min_x, min_y),
            max_x - min_x,
            max_y - min_y,
            fill=False,
            linewidth=2,
            label=name
        )
        plt.gca().add_patch(rect)

    # Fixation centers
    if not fix_df.empty:
        plt.scatter(
            fix_df["mean_x"],
            fix_df["mean_y"],
            s=120,
            c="orange",
            edgecolor="black",
            label="Fixations"
        )

    plt.gca().invert_yaxis()
    plt.legend()
    plt.title("Fixation Map with AOIs")

    analysis_dir = ensure_analysis_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(analysis_dir, f"fixation_map_{ts}.png")

    plt.savefig(out, dpi=150)
    plt.show()

    print(f"Fixation map saved → {out}")


# ======================================================
# Interactive main
# ======================================================

if __name__ == "__main__":

    print("\nGAZE ANALYSIS — INTERACTIVE MODE\n")

    csv_file = input("Path to gaze CSV file: ").strip()
    if not os.path.exists(csv_file):
        print("File not found.")
        exit()

    num_aois = int(input("How many AOIs? "))

    aois = {}

    for i in range(num_aois):
        name = input(f"\nAOI {i+1} label (e.g. Face, Text): ").strip()
        coords = []
        print("Enter 4 coordinates (x,y):")
        for j in range(4):
            x, y = map(float, input(f"  Point {j+1}: ").split(","))
            coords.append((x, y))
        aois[name] = normalize_coordinates(coords)

    threshold = float(input("\nFixation threshold seconds (default 0.5): ") or 0.5)

    fix_df = compute_fixations_multi_aoi(
        csv_file,
        aois,
        threshold
    )

    plot_fixation_map(csv_file, aois, fix_df)

    print("\n✔ Analysis complete")
