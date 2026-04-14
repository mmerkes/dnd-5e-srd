# SRD 5.2.1 Monster Parser

Parses D&D 5e System Reference Document 5.2.1 monster stat blocks from the official PDF into structured JSON.

**Output:** `output/monsters.json` — 330 monsters, all fields typed and structured.

---

## Prerequisites

- Python 3.10+
- The official SRD PDF: `SRD_CC_v5.2.1.pdf` (place in the project root)
- Install the one dependency:

```bash
pip install -r requirements.txt   # pdfplumber>=0.10.0
```

---

## Quick start

Run all three phases in sequence:

```bash
python3 run_all.py
```

This takes about 2 minutes on first run (Phase 1 reads the PDF). The final output is `output/monsters.json`.

---

## Pipeline overview

The parser is split into three phases, each producing intermediate files that the next phase reads.

```
SRD_CC_v5.2.1.pdf
    │
    ▼ python3 -m srd.phases.raw
output/raw/<slug>.txt          (one file per monster, ~330 files)
    │
    ▼ python3 -m srd.phases.sections
output/sections/<slug>.json    (labeled fields as raw strings)
    │
    ▼ python3 -m srd.phases.structured
output/monsters.json           (final — 330 structured monster objects)
```

### Resuming from a later phase

If the PDF hasn't changed, phases 1 and 2 are stable and you only need to re-run phase 3 after editing `srd/phases/structured.py`:

```bash
python3 run_all.py --start 3            # only re-run the final structuring step
python3 run_all.py --start 2            # re-run sections + structured (skip PDF read)
python3 -m srd.phases.raw --split-only  # re-split existing raw_combined.txt without re-reading PDF
```

---

## Viewing stat blocks

`viewer.py` serves a local web UI for browsing and auditing the parsed data:

```bash
python3 viewer.py           # opens on http://localhost:8080
python3 viewer.py 9090      # use a different port
```

Features:
- Search by name or creature type
- Filter by creature type and CR
- Keyboard ↑/↓ navigation through the list
- Full stat block display with all computed values (HP, initiative, passive perception, saves, skills)
- Collapsible raw JSON panel at the bottom of each stat block

No external dependencies — uses only Python's standard library.

---

## Utilities

### helpers.py — computed field functions

All values that are purely derivable from stored data are intentionally omitted from `monsters.json`.
Import `helpers.py` to compute them:

```python
from helpers import (
    ability_modifier,    # floor((score - 10) / 2)
    proficiency_bonus,   # CR → standard 5e PB
    hp_average,          # expected average HP
    hp_formula,          # e.g. "20d10+40"
    saving_throw,        # mod [+ pb [+ pb]] based on save_proficiency
    skill_bonus,         # mod + pb [+ pb] for a listed skill
    passive_perception,  # 10 + wis_mod [+ pb [+ pb]]
    damage_average,      # expected average damage roll
    damage_formula,      # e.g. "2d8+4"
    initiative_score,    # 10 + initiative_bonus
)
```

### verify.py — proficiency bonus checker

Checks every attack bonus, save DC, spell attack bonus, and spell save DC in `monsters.json`
against the standard 5e formulae and reports discrepancies:

```bash
python3 verify.py
```

Expected output: 5 discrepancies across 4 monsters — all confirmed SRD anomalies documented in `srd_bugs.md`.

---

## Data schema

Each entry in `monsters.json` is a JSON object.  A representative example:

```json
{
  "source": "SRD 5.2.1",
  "name": "Aboleth",
  "flavor_text": "",
  "size": "Large",
  "type": "Aberration",
  "tags": [],
  "alignment": "Lawful Evil",
  "armor_class": {"value": 17, "initiative_bonus": 7},
  "hit_points": {"dice_count": 20, "dice_type": 10},
  "speed": {"walk": 10, "swim": 40},
  "ability_scores": {
    "str": {"score": 21, "save_proficiency": "proficient"},
    "dex": {"score": 9},
    "con": {"score": 15, "save_proficiency": "proficient"},
    "int": {"score": 18, "save_proficiency": "proficient"},
    "wis": {"score": 15},
    "cha": {"score": 18}
  },
  "skills": {"history": "expert", "perception": "expert"},
  "damage_vulnerabilities": [],
  "damage_resistances": [],
  "damage_immunities": [],
  "condition_immunities": [],
  "senses": {"darkvision": 120},
  "languages": ["Deep Speech", "telepathy 120 ft."],
  "challenge": {"rating": "10", "xp": 5900, "xp_lair": 7200},
  "special_abilities": [...],
  "actions": [...],
  "bonus_actions": [],
  "reactions": [],
  "legendary_actions": {"description": "...", "uses": 3, "uses_lair": 4, "actions": [...]},
  "lair_actions": []
}
```

Key design notes:
- **`save_proficiency`** — present only when a stat has proficiency or expertise; absence means unproficient.
- **`skills`** — same enum pattern: `"proficient"` or `"expert"`.  Only listed skills are included.
- **`uses_per_day`** on actions — a dict: `{"uses": 3}` or `{"uses": 3, "uses_lair": 4}`.
- **`variant_of`** — present only for the 57 monsters that are variants of a base creature (e.g. all dragon age-stages).
- **Computed fields** are not stored — see `helpers.py` for HP formula, passive perception, etc.

### Repository layout

```
srd/                    ← Python package
  __init__.py
  helpers.py            ← computed-field utilities
  phases/
    __init__.py
    raw.py              ← Phase 1 (PDF → raw text)
    sections.py         ← Phase 2 (raw text → labeled sections)
    structured.py       ← Phase 3 (labeled sections → monsters.json)
data/
  corrections.json      ← manual overrides for PDF rendering artifacts
  variant_mapping.json  ← base-creature mappings for variant_of field
output/                 ← generated (gitignored)
  raw/                  ← one .txt per monster
  sections/             ← one .json per monster
  monsters.json         ← final output
run_all.py              ← pipeline entry point
verify.py               ← proficiency-bonus checker
viewer.py               ← local stat block web UI
```

See `CONTEXT.md` for full architecture documentation and `srd_bugs.md` for known SRD anomalies.

---

## Manual correction files

Two JSON files allow targeted overrides when the PDF produces unresolvable values:

- **`corrections.json`** — fixes PDF rendering artifacts (e.g. the Young White Dragon's INT saving throw renders without a minus sign in the PDF, causing it to be parsed as +2 instead of -2).
- **`variant_mapping.json`** — maps 57 monsters to their base creature for the `variant_of` field.

---

## SRD format notes (5.2.1 vs 5.1)

The 5.2.1 PDF uses a different stat block layout than the commonly documented 5.1 format:

| Field | 5.1 | 5.2.1 |
|---|---|---|
| AC | `Armor Class 17` | `AC 17 Initiative +7 (17)` |
| HP | `Hit Points 135 (18d10 + 36)` | `HP 135 (18d10 + 36)` |
| Challenge | `Challenge 9 (5,000 XP)` | `CR 9 (XP 5,000; PB +4)` |
| Ability saves | Separate "Saving Throws" line | Embedded in ability score table |
| Damage/condition immunities | Separate fields | Single `Immunities` field with semicolon separator |

---

## License

This project contains no content from the SRD PDF itself.  The SRD 5.2.1 is published under the [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/) by Wizards of the Coast.

The SRD is also available online at [dndbeyond.com/srd](https://www.dndbeyond.com/srd?srsltid=AfmBOooq9F7lNODDh6618nTRL9pgUWdUsmCpjE5ma42ieMuNEX5LaccU).
