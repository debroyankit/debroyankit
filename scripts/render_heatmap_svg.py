#!/usr/bin/env python3
"""
Render data/contributions.json (produced by fetch_contributions.py) as a proper
GitHub-style contribution heatmap SVG: a grid of rounded, colored BOXES in the
classic 53-week x 7-day calendar, revealed once with a diagonal line-after-line
slide-down (CSS keyframes, plays on load then freezes -- no looping "glow"), a
Less->More legend, and a real stats footer.

Run by .github/workflows/update-profile-art.yml after fetch_contributions.py.
"""
import datetime
import json
import os

HERE = os.path.dirname(__file__)
IN_PATH = os.path.join(HERE, "..", "data", "contributions.json")
OUT_PATH = os.path.join(HERE, "..", "contrib-heatmap.svg")

# GitHub-ish green ramp: empty -> brightest. Level 5 is a brighter neon top end.
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

CELL = 12
GAP = 3
STEP = CELL + GAP
PAD_L = 10
PAD_R = 10
PAD_T = 10
PAD_B = 10
LEFT_LABEL_W = 30
TOP_LABEL_H = 20

MUTED = "#7d8590"
TEXT = "#e6edf3"

# reveal timing (one-shot)
COL_T = 0.018   # per-column delay contribution (left -> right sweep)
ROW_T = 0.045   # per-row delay contribution (top -> bottom cascade)
CELL_DUR = 0.42


def level_for(count):
    if count == 0:
        return 0
    if count <= 5:
        return 1
    if count <= 15:
        return 2
    if count <= 30:
        return 3
    if count <= 50:
        return 4
    return 5


def build_grid(days):
    first = datetime.date.fromisoformat(days[0]["date"])
    lead_pad = (first.weekday() + 1) % 7  # sunday=0
    grid = []
    col = [None] * lead_pad
    for d in days:
        date = datetime.date.fromisoformat(d["date"])
        weekday = (date.weekday() + 1) % 7
        while len(col) < weekday:
            col.append(None)
        col.append((d["date"], d["count"], level_for(d["count"])))
        if len(col) == 7:
            grid.append(col)
            col = []
    if col:
        while len(col) < 7:
            col.append(None)
        grid.append(col)
    return grid


def render(data):
    days = data["days"]
    grid = build_grid(days)
    n_cols = len(grid)
    art_w = n_cols * STEP
    art_h = 7 * STEP

    month_labels = []
    seen_months = set()
    prev_ci = -999
    for ci, column in enumerate(grid):
        first_date = None
        for cell in column:
            if cell is not None:
                first_date = datetime.date.fromisoformat(cell[0])
                break
        if first_date is None:
            continue
        
        key = (first_date.year, first_date.month)
        should_label = False
        if key not in seen_months:
            if ci == 0:
                should_label = True
            elif first_date.day <= 7:
                if ci - prev_ci >= 2:
                    should_label = True
        
        if should_label:
            seen_months.add(key)
            month_labels.append((ci, first_date.strftime("%b")))
            prev_ci = ci

    grid_top = PAD_T + TOP_LABEL_H
    grid_left = PAD_L + LEFT_LABEL_W
    canvas_w = grid_left + art_w - GAP + PAD_R
    canvas_h = grid_top + art_h + 12 + CELL + PAD_B

    css = f"""
@keyframes cell {{
  0%   {{ opacity: 0; transform: translateY(-6px); }}
  100% {{ opacity: 1; transform: translateY(0); }}
}}
.c {{ opacity: 0; animation: cell {CELL_DUR:.2f}s cubic-bezier(.2,.8,.2,1) both; }}
""".strip()

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" font-family="-apple-system, BlinkMacSystemFont, \'Segoe UI\', Helvetica, Arial, sans-serif, \'Apple Color Emoji\', \'Segoe UI Emoji\'">',
        f'<style>{css}</style>',
    ]

    for ci, label in month_labels:
        x = grid_left + ci * STEP
        parts.append(f'<text x="{x}" y="{PAD_T + 14}" fill="{MUTED}" font-size="10">{label}</text>')

    for wi, wname in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = grid_top + wi * STEP + CELL * 0.78
        parts.append(f'<text x="{PAD_L}" y="{y:.1f}" fill="{MUTED}" font-size="9">{wname}</text>')

    # the boxes -- each a rounded rect, diagonal slide-down reveal (once, freeze)
    for ci, column in enumerate(grid):
        gx = grid_left + ci * STEP
        for ri, cell in enumerate(column):
            if cell is None:
                continue
            date_s, count, lvl = cell
            gy = grid_top + ri * STEP
            delay = ci * COL_T + ri * ROW_T
            plural = "s" if count != 1 else ""
            parts.append(
                f'<rect class="c" x="{gx}" y="{gy}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'fill="{PALETTE[lvl]}" style="animation-delay:{delay:.3f}s">'
                f'<title>{date_s}: {count} contribution{plural}</title></rect>'
            )

    # Legend & stats row below the grid
    footer_y = grid_top + art_h + 12
    total = data["total_contributions"]
    
    # Left-aligned total contributions count
    parts.append(f'<text x="{grid_left}" y="{footer_y + CELL*0.8:.1f}" fill="{TEXT}" font-size="12" font-weight="700">'
                 f'{total:,} contributions in the last year</text>')

    # Align the legend on the right edge of the grid
    grid_right = grid_left + art_w - GAP
    leg_width = 147
    leg_x = grid_right - leg_width
    
    parts.append(f'<text x="{leg_x}" y="{footer_y + CELL*0.8:.1f}" fill="{MUTED}" font-size="10" text-anchor="start">Less</text>')
    lx = leg_x + 28
    for lvl, color in enumerate(PALETTE):
        parts.append(f'<rect x="{lx}" y="{footer_y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{color}"/>')
        lx += STEP
    parts.append(f'<text x="{lx + 3}" y="{footer_y + CELL*0.8:.1f}" fill="{MUTED}" font-size="10" text-anchor="start">More</text>')

    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    with open(IN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    svg = render(data)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {OUT_PATH} ({len(svg)} bytes)")