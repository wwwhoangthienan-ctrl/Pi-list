"""
Pi Viewer backend — reference implementation.

Serves:
  GET /digits?start=<int>&count=<int>        -> {"content": "141592..."}
  GET /search?pattern=<digits>                -> {"matches": [pos, pos, ...]}
  GET /search_grid?pattern=1,2,3,,5/...&width=5  -> {"matches": [pos, ...]}
      (5x5 pattern search: pattern rows separated by "/", cells by ",",
       empty cell = wildcard. width = row width used to "wrap" the 1D
       digit stream into a 2D grid before matching.)

Run locally:  pip install flask
              python pi_backend.py
Then point your Roblox HttpService calls at wherever you deploy this
(Render, Fly.io, a VPS, etc). Roblox can't call localhost.

IMPORTANT ON SCALE:
This demo computes/loads digits into one string in memory. That's fine
up to a few million digits. For 10M-1B you want:
  1. A precomputed digit file (e.g. from https://stuff.mit.edu/afs/sipb/contrib/pi/
     which has a public 1-billion-digit file), streamed/mmap'd from disk
     instead of loaded fully into RAM.
  2. A suffix array or FM-index built once offline for fast substring
     search (this is what PiSearch does — see github.com/JoshKeegan/PiSearch
     for the algorithm approach). Naive string search on a billion
     characters per request will be too slow for a game.
This file gives you a correct, working small-scale version so you can
build and test the whole pipeline (Roblox <-> API contract) today, and
swap in the real 1B-digit indexed backend later without changing the
Roblox client at all.
"""

from flask import Flask, request, jsonify
from mpmath import mp

app = Flask(__name__)

# --- Demo digit source: computes & caches up to DIGIT_LIMIT digits. ---
# Swap this out for a file-backed / mmap'd billion-digit source in prod.
DIGIT_LIMIT = 1_000_000
mp.dps = DIGIT_LIMIT + 10
PI_DIGITS = mp.nstr(mp.pi, DIGIT_LIMIT + 1, strip_zeros=False).replace(".", "")


@app.route("/digits")
def digits():
    start = int(request.args.get("start", 0))
    count = min(int(request.args.get("count", 1000)), 1000)  # match pi.delivery's cap
    if start < 0 or start >= len(PI_DIGITS):
        return jsonify({"error": "start out of range"}), 400
    chunk = PI_DIGITS[start:start + count]
    return jsonify({"start": start, "count": len(chunk), "content": chunk})


@app.route("/search")
def search():
    pattern = request.args.get("pattern", "")
    limit = int(request.args.get("limit", 50))
    if not pattern.isdigit():
        return jsonify({"error": "pattern must be digits only"}), 400
    matches = []
    idx = PI_DIGITS.find(pattern)
    while idx != -1 and len(matches) < limit:
        matches.append(idx)
        idx = PI_DIGITS.find(pattern, idx + 1)
    return jsonify({"pattern": pattern, "matches": matches})


@app.route("/search_grid")
def search_grid():
    """
    Reshapes the digit stream into rows of `width` digits, then looks
    for the given 2D pattern (rows separated by '/', cells by ',',
    blank cell = wildcard). Designed for small patterns like 5x5.
    """
    width = int(request.args.get("width", 5))
    raw_pattern = request.args.get("pattern", "")
    rows = [r.split(",") for r in raw_pattern.split("/")]
    p_h, p_w = len(rows), len(rows[0]) if rows else 0

    total_rows = len(PI_DIGITS) // width
    matches = []
    limit = int(request.args.get("limit", 20))

    for r in range(total_rows - p_h + 1):
        for c in range(width - p_w + 1):
            ok = True
            for pr in range(p_h):
                for pc in range(p_w):
                    cell = rows[pr][pc]
                    if cell == "":
                        continue
                    pos = (r + pr) * width + (c + pc)
                    if pos >= len(PI_DIGITS) or PI_DIGITS[pos] != cell:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                matches.append(r * width + c)
                if len(matches) >= limit:
                    return jsonify({"matches": matches})
    return jsonify({"matches": matches})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
