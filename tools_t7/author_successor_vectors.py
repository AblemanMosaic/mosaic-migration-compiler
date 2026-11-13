"""Renew implementation-bound vectors while preserving their exact predecessors."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tools.common import read_json, save_json
from tools_t2.check_vectors import invoke as invoke_t2
from tools_t3.author_vectors import author as author_t3


def main() -> int:
    predecessor = read_json(ROOT / "provenance/turn7/PREDECESSOR-T2-KNOWN-ANSWERS.json")
    successor = deepcopy(predecessor)
    successor["claim"] = "Successor implementation-bound records after portable path-order repair; predecessor preserved under provenance/turn7."
    for case in successor["cases"]:
        case["expected"] = invoke_t2(case)
    save_json(ROOT / "interop/t2-known-answers.json", successor)
    save_json(ROOT / "interop/t3-known-answers.json", author_t3())
    print("renewed T2 and T3 implementation-bound vectors; predecessors retained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
