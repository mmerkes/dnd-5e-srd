#!/usr/bin/env python3
"""
Run all parsing phases in sequence.

Monster pipeline (Phases 1–3):
  Phase 1  — extract raw monster text from PDF
  Phase 2  — label monster sections
  Phase 3  — build output/monsters.json

Spell pipeline (Phases 4–6):
  Phase 4  — extract raw spell text from PDF
  Phase 5  — label spell sections
  Phase 6  — build output/spells.json

Magic Items pipeline (Phases 7–9)   — stub, not yet implemented
Feats pipeline     (Phases 10–12)   — stub, not yet implemented
Classes pipeline   (Phases 13–15)   — stub, not yet implemented
Species pipeline   (Phases 16–18)   — stub, not yet implemented
Origins pipeline   (Phases 19–21)   — stub, not yet implemented

Usage:
  python3 run_all.py                   # run all 21 phases
  python3 run_all.py --start 4         # resume from a specific phase number
  python3 run_all.py --monsters        # run only monster phases (1–3)
  python3 run_all.py --spells          # run only spell phases (4–6)
  python3 run_all.py --magic-items     # run only magic item phases (7–9)
  python3 run_all.py --feats           # run only feat phases (10–12)
  python3 run_all.py --classes         # run only class phases (13–15)
  python3 run_all.py --species         # run only species phases (16–18)
  python3 run_all.py --origins         # run only origins phases (19–21)
"""

import subprocess
import sys

# Each phase is invoked as a module so paths inside the package resolve correctly.
PHASES = [
    ("Phase 1  — extract raw monster text",        "srd.phases.raw"),
    ("Phase 2  — label monster sections",          "srd.phases.sections"),
    ("Phase 3  — build monsters.json",             "srd.phases.structured"),
    ("Phase 4  — extract raw spell text",          "spells.phases.raw"),
    ("Phase 5  — label spell sections",            "spells.phases.sections"),
    ("Phase 6  — build spells.json",               "spells.phases.structured"),
    ("Phase 7  — extract raw magic item text",     "magic_items.phases.raw"),
    ("Phase 8  — label magic item sections",       "magic_items.phases.sections"),
    ("Phase 9  — build magic_items.json",          "magic_items.phases.structured"),
    ("Phase 10 — extract raw feat text",           "feats.phases.raw"),
    ("Phase 11 — label feat sections",             "feats.phases.sections"),
    ("Phase 12 — build feats.json",                "feats.phases.structured"),
    ("Phase 13 — extract raw class text",          "classes.phases.raw"),
    ("Phase 14 — label class sections",            "classes.phases.sections"),
    ("Phase 15 — build classes.json",              "classes.phases.structured"),
    ("Phase 16 — extract raw species text",        "species.phases.raw"),
    ("Phase 17 — label species sections",          "species.phases.sections"),
    ("Phase 18 — build species.json",              "species.phases.structured"),
    ("Phase 19 — extract raw origins text",        "origins.phases.raw"),
    ("Phase 20 — label origins sections",          "origins.phases.sections"),
    ("Phase 21 — build origins.json",              "origins.phases.structured"),
]

# Section-flag → (start_phase, end_phase) — 1-indexed
SECTION_FLAGS = {
    "--monsters":    (1,  3),
    "--spells":      (4,  6),
    "--magic-items": (7,  9),
    "--feats":       (10, 12),
    "--classes":     (13, 15),
    "--species":     (16, 18),
    "--origins":     (19, 21),
}

start = 1
end   = len(PHASES)

for flag, (s, e) in SECTION_FLAGS.items():
    if flag in sys.argv:
        start, end = s, e
        break

if "--start" in sys.argv:
    idx = sys.argv.index("--start")
    try:
        start = int(sys.argv[idx + 1])
    except (IndexError, ValueError):
        flags = " | ".join(SECTION_FLAGS)
        print(f"Usage: python3 run_all.py [--start <1–{len(PHASES)}>] [{flags}]")
        sys.exit(1)

for phase_num, (label, module) in enumerate(PHASES, start=1):
    if phase_num < start or phase_num > end:
        print(f"Skipping {label}", flush=True)
        continue

    print(f"\n{'=' * 60}", flush=True)
    print(f"  {label}", flush=True)
    print(f"{'=' * 60}", flush=True)

    result = subprocess.run([sys.executable, "-m", module])
    if result.returncode != 0:
        print(f"\nFailed at {module} (exit code {result.returncode}).")
        print(f"Fix the issue, then re-run with:  python3 run_all.py --start {phase_num}")
        sys.exit(1)

print("\n" + "=" * 60)
print("  All phases complete.")
print("  Outputs: output/monsters.json  output/spells.json")
print("           (magic_items, feats, classes, species, origins: not yet implemented)")
print("=" * 60)
