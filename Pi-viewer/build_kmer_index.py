"""
build_kmer_index.py — run this ONCE, offline, against your digit file.

Builds an inverted index: every K-digit window -> sorted list of
positions where it occurs. Because the alphabet is only 10 symbols,
this stays small even at 1B digits (10^K possible keys), and search
becomes "look up the first K digits of the pattern, then verify each
candidate" instead of scanning a billion characters.

Output: two files next to your digit file:
  <name>.index.json   -- {kmer: [pos, pos, ...]}   (fine up to ~10-50M digits)
  For real billion-digit scale, swap the JSON dump for a packed binary
  format (see NOTES at bottom) — JSON gets slow/huge past that.

Usage:
  python build_kmer_index.py pi_digits.txt --k 6
"""

import argparse
import json
import sys
from collections import defaultdict


def build_index(digits: str, k: int):
    index = defaultdict(list)
    n = len(digits)
    for i in range(n - k + 1):
        key = digits[i:i + k]
        index[key].append(i)
    return index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("digit_file")
    parser.add_argument("--k", type=int, default=6, help="k-mer window size")
    args = parser.parse_args()

    with open(args.digit_file) as f:
        digits = f.read().strip()

    print(f"Indexing {len(digits)} digits with k={args.k}...", file=sys.stderr)
    index = build_index(digits, args.k)

    out_path = args.digit_file + f".k{args.k}.index.json"
    with open(out_path, "w") as f:
        json.dump(index, f)

    print(f"Wrote {len(index)} unique {args.k}-mers to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

# ---- NOTES for scaling past ~10-50M digits ----
# JSON becomes slow to load/parse at real 1B scale. At that point:
#   - Store positions as raw binary arrays (Python `array('I', positions)`
#     or numpy uint32/uint64) instead of JSON lists.
#   - Store the index as one file per k-mer prefix (e.g. shard by first
#     2 digits into 100 files) so you never load the whole thing at once.
#   - Or use a proper embedded key-value store (LMDB, RocksDB) mapping
#     kmer -> packed position bytes, queried on demand instead of
#     loaded fully into memory.
# The search_server.py in this folder is written against the JSON
# format for clarity — swapping the storage layer only touches
# `load_index()` and `lookup()`, nothing else.
