"""Execution evidence: run each stage of query.py and save its console output
as terminal-style PNGs (mongodb/screenshots/<step>_<n>.png) for the report.

Run: python3 mongodb/screenshots.py
"""

import re
import subprocess
import textwrap
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
OUT = HERE / "screenshots"
OUT.mkdir(exist_ok=True)
MAX_LINES = 30  # longer tables are cut in the image; the full table is in results/

STEPS = ["S1", "S2", "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10", "CHECK"]


def render(lines, path):
    width = max(len(l) for l in lines)
    fig = plt.figure(figsize=(max(7, width * 0.074 + 0.3), 0.19 * len(lines) + 0.35))
    fig.patch.set_facecolor("#1e1f22")
    for i, line in enumerate(lines):
        color = "#d4d4d4"
        if line.startswith("$ "):
            color = "#7ec699"
        elif line.startswith("---"):
            color = "#79b8ff"
        elif line.startswith("[test]"):
            color = "#f0c674"
        elif line.startswith("[output"):
            color = "#9a9a9a"
        fig.text(0.15 / fig.get_figwidth(), 1 - (i + 0.9) / (len(lines) + 0.8), line, family="Menlo", fontsize=8.6, color=color,
                 va="baseline")
    fig.savefig(path, dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)


for step in STEPS:
    out = subprocess.run([sys.executable, str(HERE / "query.py"), step], capture_output=True, text=True, check=True).stdout
    # Split into one block per result table; [test] lines stay with the table above.
    blocks = re.split(r"\n(?=--- )", out.strip())
    for n, block in enumerate(blocks, 1):
        lines = block.strip("\n").splitlines()
        if len(lines) > MAX_LINES:
            title = re.sub(r"^--- (\S+).*", r"\1", lines[0])
            hidden = len(lines) - MAX_LINES
            tail = [l for l in lines[MAX_LINES:] if l.startswith("[test]")]
            lines = lines[:MAX_LINES] + [f"[output shortened for the screenshot: {hidden} more rows; full table in mongodb/results/]"] + tail
        wrapped = []
        for l in lines:  # wrap long sentences (test results), never table rows
            if len(l) > 100 and (l.startswith("[") or not l.startswith(" ")) and "  " not in l.strip():
                wrapped += textwrap.wrap(l, 100, subsequent_indent="       ")
            else:
                wrapped.append(l.rstrip())
        lines = [f"$ python3 mongodb/query.py {step}", ""] + wrapped
        render(lines, OUT / f"{step.lower()}_{n}.png")
    print(f"{step}: {len(blocks)} screenshot(s)")
