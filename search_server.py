"""
search_server.py — serves digits and search using a self-built index.

Same API contract as the earlier pi_backend.py demo, so the Roblox
client (DigitService.lua) doesn't need to change at all:

  GET /digits?start=<int>&count=<int>
  GET /search?pattern=<digits>
  GET /search_grid?pattern=<rows>&width=<int>

Difference from the demo: this mmaps the digit file (never loads the
whole thing into RAM) and uses the k-mer index for search instead of
a naive linear scan, so it stays fast even at hundreds of millions+
digits.

Usage:
  python build_kmer_index.py pi_digits.txt --k 6
  python search_server.py pi_digits.txt --k 6
"""

import argparse
import json
import mmap
import sys

from flask import Flask, request, jsonify

app = Flask(__name__)

STATE = {}


def load_index(path, k):
    with open(path) as f:
        raw = json.load(f)
    return raw


def get_mmap(path):
    f = open(path, "rb")
    return mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)


def read_digits(start, count):
    mm = STATE["mmap"]
    end = min(start + count, len(mm))
    return mm[start:end].decode("ascii")


def search_pattern(pattern):
    k = STATE["k"]
    index = STATE["index"]
    if len(pattern) < k:
        # pattern shorter than our index window — fall back to
        # scanning candidates for the shortest known prefix key,
        # fine since k is small (e.g. 6).
        prefix_candidates = [p for key, positions in index.items()
                              if key.startswith(pattern) for p in positions]
        return sorted(prefix_candidates)[:50]

    key = pattern[:k]
    candidates = index.get(key, [])
    matches = []
    for pos in candidates:
        chunk = read_digits(pos, len(pattern))
        if chunk == pattern:
            matches.append(pos)
        if len(matches) >= 50:
            break
    return matches


@app.route("/digits")
def digits():
    start = int(request.args.get("start", 0))
    count = min(int(request.args.get("count", 1000)), 1000)
    if start < 0 or start >= len(STATE["mmap"]):
        return jsonify({"error": "start out of range"}), 400
    return jsonify({"start": start, "content": read_digits(start, count)})


@app.route("/search")
def search():
    pattern = request.args.get("pattern", "")
    if not pattern.isdigit():
        return jsonify({"error": "pattern must be digits only"}), 400
    return jsonify({"pattern": pattern, "matches": search_pattern(pattern)})


@app.route("/search_grid")
def search_grid():
    width = int(request.args.get("width", 5))
    raw_pattern = request.args.get("pattern", "")
    rows = [r.split(",") for r in raw_pattern.split("/")]
    p_h, p_w = len(rows), len(rows[0]) if rows else 0
    limit = int(request.args.get("limit", 20))

    matches = []

    def verify(row_index, col):
        if col + p_w > width:
            return False  # pattern would wrap past the row edge, not a valid grid position
        for pr in range(p_h):
            for pc in range(p_w):
                cell = rows[pr][pc]
                if cell == "":
                    continue
                grid_pos = (row_index + pr) * width + (col + pc)
                if read_digits(grid_pos, 1) != cell:
                    return False
        return True

    # Find any fully-known (no wildcard) row in the pattern to use as
    # a fast anchor via the k-mer index — doesn't have to be row 0.
    anchor_row_idx = next((i for i, row in enumerate(rows) if "" not in row), None)

    if anchor_row_idx is not None:
        anchor_str = "".join(rows[anchor_row_idx])
        for pos in search_pattern(anchor_str):
            row_index = (pos // width) - anchor_row_idx
            col = pos % width
            if row_index < 0:
                continue
            top_left = row_index * width + col
            if verify(row_index, col):
                matches.append(top_left)
                if len(matches) >= limit:
                    break
    else:
        # Every row has a wildcard — no fast anchor available, so this
        # is a brute-force scan. Fine for small/medium digit counts;
        # for real billion-digit scale, either require at least one
        # fully-known row in the UI, or precompute a secondary index.
        total_rows = len(STATE["mmap"]) // width
        for r in range(total_rows - p_h + 1):
            for c in range(width - p_w + 1):
                if verify(r, c):
                    matches.append(r * width + c)
                    if len(matches) >= limit:
                        return jsonify({"matches": matches})

    return jsonify({"matches": matches})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("digit_file")
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    STATE["k"] = args.k
    STATE["mmap"] = get_mmap(args.digit_file)
    STATE["index"] = load_index(args.digit_file + f".k{args.k}.index.json", args.k)

    print(f"Loaded {len(STATE['mmap'])} digits, {len(STATE['index'])} k-mers", file=sys.stderr)
    app.run(host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
