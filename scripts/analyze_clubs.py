#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Поиск пар названий клубов с похожестью по символам (> заданного порога).

Зависимости: только стандартная библиотека.
Пример:
  curl -sS "https://calc.figurebase.ru/api/clubs" -o /tmp/clubs.json
  python3 scripts/analyze_clubs.py /tmp/clubs.json /tmp/clubs_similar.txt

Или с порогом 0.75:
  python3 scripts/analyze_clubs.py /tmp/clubs.json -o /tmp/out.txt -t 0.75
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from itertools import combinations


def lev(a: str, b: str) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins, delete, sub = cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def dice_chars(a: str, b: str) -> float:
    if len(a) + len(b) == 0:
        return 1.0
    ca, cb = Counter(a), Counter(b)
    inter = sum((ca & cb).values())
    return 2 * inter / (len(a) + len(b))


def lev_ratio(a: str, b: str) -> float:
    mx = max(len(a), len(b))
    if mx == 0:
        return 1.0
    return 1.0 - lev(a, b) / mx


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Пары клубов с max(Dice по символам, Lev ratio) > порога",
    )
    parser.add_argument(
        "json_path",
        help="JSON массив клубов (как /api/clubs)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="файл отчёта (UTF-8); по умолчанию — stdout",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=0.70,
        help="порог похожести (по умолчанию 0.70)",
    )
    args = parser.parse_args()

    with open(args.json_path, encoding="utf-8") as f:
        clubs = json.load(f)

    pairs: list[tuple[float, float, float, dict, dict]] = []
    for i, j in combinations(range(len(clubs)), 2):
        a = clubs[i]["name"].lower().strip()
        b = clubs[j]["name"].lower().strip()
        if a == b:
            continue
        d = dice_chars(a, b)
        lr = lev_ratio(a, b)
        m = max(d, lr)
        if m > args.threshold:
            pairs.append((m, d, lr, clubs[i], clubs[j]))

    pairs.sort(reverse=True, key=lambda x: x[0])

    lines: list[str] = []
    for m, d, lr, ci, cj in pairs:
        lines.append("---")
        lines.append(f"Dice={d:.3f} Lev_ratio={lr:.3f} max={m:.3f}")
        lines.append(f"ID {ci['id']}: {ci['name']}")
        lines.append(f"ID {cj['id']}: {cj['name']}")
    lines.append(f"TOTAL {len(pairs)}")
    text = "\n".join(lines) + "\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
