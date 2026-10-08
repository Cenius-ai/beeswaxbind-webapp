#!/usr/bin/env bash
#
# Non-interactive tour of BeeswaxBind: every calculator, both drive modes.
# The platform records this script, so it prints real numbers and exits 0.
#
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
BB=("$PYTHON" beeswaxbind.py)

run() {
  printf '\n$ beeswaxbind %s\n' "$*"
  "${BB[@]}" "$@"
}

run --version

run needle --thread 18/3 --leather 4oz
run needle --thread 25/3 --leather 2mm --units metric

run tension --spi 6 --thread 18/3 --leather 4oz
run tension --length 4mm --thread 30/3 --leather 8oz

run wax --parts 5:1 --batch 100g
run wax --preset hard --batch 2oz

run reference --search 18/3
run needle --thread 18/3 --json

printf '\n$ beeswaxbind   (prompt-and-answer wizard, answers piped in)\n'
"${BB[@]}" < examples/wizard-answers.txt

printf '\nDemo complete.\n'
