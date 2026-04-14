# SRD Parser — Roadmap

## Current state
- **`output/monsters.json`** — 330 monsters, fully parsed and structured.
- **`output/spells.json`** — 339 spells, fully parsed and structured.
- All derivable monster fields removed from JSON; `helpers.py` provides computed helpers.
- `verify.py` confirms 5 discrepancies across 4 monsters — all known SRD anomalies.
- `viewer.py` (combined viewer, port 8080) shows 7 tabs: Monsters, Spells, and 5 stubs.
- Stub pipelines exist for: Magic Items, Feats, Classes, Species, Origins (phases 7–21).
  Each stub prints "not yet implemented" — no data is parsed yet.
- `uses_per_day` field on monster actions stores `{"uses": N, ["uses_lair": M], ["each": true]}`.
- See `CONTEXT.md` for full architecture details and known issues.

---

## Completed work

### Monster pipeline ✅

**Phase 1 — Raw extraction** (`srd/phases/raw.py`)
pdfplumber two-column extraction; dynamic column-split detection; footer stripping;
SIZES regex handles "Medium or Small" compound sizes for NPC archetypes and lycanthropes.
`--split-only` flag for fast re-splits.

**Phase 2 — Section labeling** (`srd/phases/sections.py`)
Extracts AC, HP, speed, ability scores (with embedded saving throws), skills, senses, CR, etc.

**Phase 3 — Structured JSON** (`srd/phases/structured.py`)
- All stat block fields deep-parsed into typed values
- Spellcasting sub-structure (`parse_spellcasting()`): 41 monsters
- Multiattack sub-structure (`parse_multiattack()`): 154/155 monsters (Hydra excepted)
- Variant tagging: 57 monsters via `data/variant_mapping.json`
- Source: `"source": "SRD 5.2.1"` on every object
- `verify.py`: 5 discrepancies across 4 monsters — all confirmed SRD anomalies (see `srd_bugs.md`)

### Spell pipeline ✅

**Phase 4 — Raw extraction** (`spells/phases/raw.py`)
Font-aware SC700 char-level extraction for `GillSans-SemiBold-SC700` spell names (two-pass:
SC700 chars → names, non-SC700 body chars excluding SC700 y-ranges → body text).
Sort by exact `(top, x0)` — NOT quantized. `_BODY_Y_TOL=2` to keep inline headers separate.
Carry-over artifact removal: blocks extend to next meta line, next-spell name filtered.

**Phase 5 — Section labeling** (`spells/phases/sections.py`)
Happy-path primary regex `^Label:[ \t]*(.+)$` (note `[ \t]*` not `\s*` — prevents crossing newlines).
Queue-based fallback for Chill Touch (Cambria-Bold labels on separate lines; values interleaved).
Handles: `Component:` singular, wrapped casting times, `_split_at_inline_header()` for
"Cantrip Upgrade." and "Using a Higher-Level Spell Slot." headers.

**Phase 6 — Structured JSON** (`spells/phases/structured.py`)
Components parsed into `verbal/somatic/material/material_desc`. Duration parsed into
`concentration` flag + bare `duration`. Description text normalized (soft hyphen join,
whitespace collapse). `data/spell_corrections.json` patches False Life.

**Combined viewer** (`viewer.py`): stdlib-only HTTP server, port 8080. Monster and spell tabs
in one page (M/S keyboard shortcut to switch). Monster tab: type/CR filters, parchment stat blocks,
client-side computed values. Spell tab: level/school/class/concentration filters, spell cards.

---

## Open / future work

### A. Embedded spell stat blocks (Medium priority)
3 spells have embedded creature stat blocks in `embedded_stat_blocks` (raw strings):
Animate Objects, Giant Insect, Summon Dragon.
Could be deep-parsed using the monster structured parser → `"summoned_creatures": [...]`.

### B. TypeScript types (Low priority)
TypeScript interfaces for `monsters.json` and `spells.json` for type-safe frontend use.

### C. SQLite loader (Low priority)
Normalized SQLite DB: `monsters`, `monster_actions`, `monster_damage_rolls`, `spells`, `spell_classes`.
Enables queries like "find all CR 5–10 undead with darkvision > 60 ft".

### D. Stub pipelines — implement any of these to add a new content type (Low priority)
Stubs exist for all 5 types — each has `__init__.py` + 3 phase files that print "not yet implemented".
The viewer tab and `run_all.py` section flag are already wired up; just implement the phases.

**Magic Items** (phases 7–9): `magic_items/phases/{raw,sections,structured}.py`
- Fields to extract: name, type (Armor/Weapon/Wondrous/etc.), rarity, attunement required, description
- Run with: `python3 run_all.py --magic-items`
- Output: `output/magic_items.json`

**Feats** (phases 10–12): `feats/phases/{raw,sections,structured}.py`
- Fields to extract: name, prerequisite, description, benefit
- Run with: `python3 run_all.py --feats`
- Output: `output/feats.json`

**Classes** (phases 13–15): `classes/phases/{raw,sections,structured}.py`
- Complex nested structure: class features, subclasses, level tables
- Run with: `python3 run_all.py --classes`
- Output: `output/classes.json`

**Species** (phases 16–18): `species/phases/{raw,sections,structured}.py`
- Fields to extract: name, size, speed, traits, language
- Run with: `python3 run_all.py --species`
- Output: `output/species.json`

**Origins / Backgrounds** (phases 19–21): `origins/phases/{raw,sections,structured}.py`
- Fields to extract: name, ability score increases, skill proficiencies, feat, equipment, description
- Run with: `python3 run_all.py --origins`
- Output: `output/origins.json`

### E. Rules Glossary (Low priority)
Condition definitions (Blinded, Frightened, etc.) — no stub yet.

---

## Suggested next session start

1. Read `CONTEXT.md` for architecture details.
2. Run `python3 run_all.py --start 5` to confirm clean 339-spell output.
3. Run `python3 verify.py` to confirm 5 discrepancies (all known SRD anomalies).
4. Run `python3 viewer.py` and verify all 7 tabs load (5 show "not yet implemented" placeholder).
5. Pick up at A, B, C/D (stub pipelines), or E above.

## Quick reference — running the pipeline
```bash
python3 run_all.py                  # all 21 phases (phases 1 + 4 re-read PDF, ~2 min each)
python3 run_all.py --monsters       # monster phases only (1–3)
python3 run_all.py --spells         # spell phases only (4–6)
python3 run_all.py --magic-items    # magic item phases only (7–9, stub)
python3 run_all.py --feats          # feat phases only (10–12, stub)
python3 run_all.py --classes        # class phases only (13–15, stub)
python3 run_all.py --species        # species phases only (16–18, stub)
python3 run_all.py --origins        # origins phases only (19–21, stub)
python3 run_all.py --start 2        # monster sections + structured (skip PDF)
python3 run_all.py --start 3        # monster structured only
python3 run_all.py --start 5        # spell sections + structured (skip PDF)
python3 run_all.py --start 6        # spell structured only
python3 viewer.py                   # combined viewer → http://localhost:8080
python3 verify.py                   # monster PB verification
```
