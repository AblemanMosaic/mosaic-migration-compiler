#!/bin/sh
set -eu
[ "$#" -eq 2 ] || { echo 'usage: replay_posix.sh EXPECTED_SOURCE OUTSIDE_OUTPUT' >&2; exit 2; }
SOURCE=$1
OUT=$2
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
for PHASE in test-t1 test-t2 test-t3 test-t4 test-t5 base-tests scenarios examples base-audit base-assemble test-t6 audit assemble; do
  python tools_t6/qualify.py --expected-source "$SOURCE" --out "$OUT" --phase "$PHASE"
done
