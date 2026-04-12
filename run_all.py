#!/usr/bin/env python3
"""
Run all three parsing phases in sequence.

Usage:  python3 run_all.py
        python3 run_all.py --start 2   # resume from Phase 2 or 3
"""

import subprocess
import sys

# Each phase is invoked as a module so paths inside the package resolve correctly.
PHASES = [
    ("Phase 1 — extract raw text",      "srd.phases.raw"),
    ("Phase 2 — label sections",        "srd.phases.sections"),
    ("Phase 3 — build structured JSON", "srd.phases.structured"),
]

start = 1
if "--start" in sys.argv:
    idx = sys.argv.index("--start")
    try:
        start = int(sys.argv[idx + 1])
    except (IndexError, ValueError):
        print("Usage: python3 run_all.py [--start <1|2|3>]")
        sys.exit(1)

for phase_num, (label, module) in enumerate(PHASES, start=1):
    if phase_num < start:
        print(f"Skipping {label}")
        continue

    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")

    result = subprocess.run([sys.executable, "-m", module])
    if result.returncode != 0:
        print(f"\nFailed at {module} (exit code {result.returncode}).")
        print(f"Fix the issue, then re-run with:  python3 run_all.py --start {phase_num}")
        sys.exit(1)

print("\n" + "=" * 60)
print("  All phases complete.")
print("  Final output: output/monsters.json")
print("=" * 60)
