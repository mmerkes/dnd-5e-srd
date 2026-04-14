# SRD Parser — Session Context

## What this project does
Parses D&D 5e SRD 5.2.1 (`SRD_CC_v5.2.1.pdf`) into structured JSON.

- **`output/monsters.json`** — 330 monsters, all fields typed and parsed
- **`output/spells.json`** — 339 spells, all fields typed and parsed

## File structure
```
srd/
  __init__.py
  helpers.py            Monster computed-field utilities (ability_modifier, etc.)
  phases/
    __init__.py
    raw.py              Phase 1 — PDF extraction → output/raw/<slug>.txt
    sections.py         Phase 2 — Section labeling → output/sections/<slug>.json
    structured.py       Phase 3 — Deep parsing → output/monsters.json

spells/
  __init__.py
  phases/
    __init__.py
    raw.py              Phase 4 — PDF extraction → output/spells/raw/<slug>.txt
    sections.py         Phase 5 — Section labeling → output/spells/sections/<slug>.json
    structured.py       Phase 6 — Deep parsing → output/spells.json

magic_items/            STUB — phases 7–9, not yet implemented
  __init__.py
  phases/
    __init__.py
    raw.py              Phase 7  — stub (prints "not yet implemented")
    sections.py         Phase 8  — stub
    structured.py       Phase 9  — stub → output/magic_items.json (when done)

feats/                  STUB — phases 10–12, not yet implemented
  __init__.py
  phases/
    __init__.py
    raw.py              Phase 10 — stub
    sections.py         Phase 11 — stub
    structured.py       Phase 12 — stub → output/feats.json (when done)

classes/                STUB — phases 13–15, not yet implemented
  __init__.py
  phases/
    __init__.py
    raw.py              Phase 13 — stub
    sections.py         Phase 14 — stub
    structured.py       Phase 15 — stub → output/classes.json (when done)

species/                STUB — phases 16–18, not yet implemented
  __init__.py
  phases/
    __init__.py
    raw.py              Phase 16 — stub
    sections.py         Phase 17 — stub
    structured.py       Phase 18 — stub → output/species.json (when done)

origins/                STUB — phases 19–21, not yet implemented (character backgrounds)
  __init__.py
  phases/
    __init__.py
    raw.py              Phase 19 — stub
    sections.py         Phase 20 — stub
    structured.py       Phase 21 — stub → output/origins.json (when done)

data/
  variant_mapping.json  Manual variant_of mappings (57 entries) loaded by srd/phases/structured.py
  corrections.json      Manual corrections for monster PDF artifacts (e.g. unsigned saving throws)
  spell_corrections.json  Manual corrections for spell PDF artifacts (e.g. False Life)

run_all.py            Runs all 21 phases; supports --start N and section flags
                        (--monsters, --spells, --magic-items, --feats, --classes, --species, --origins)
verify.py             Proficiency-bonus checker for monsters; reports SRD discrepancies
viewer.py             Combined viewer (all content types) — python3 viewer.py → http://localhost:8080
spell_viewer.py       Standalone spell viewer (legacy) — python3 spell_viewer.py → http://localhost:8081
srd_bugs.md           Confirmed SRD typos and non-standard values
requirements.txt      pdfplumber>=0.10.0
output/
  raw_combined.txt      Full extracted monster text (debugging)
  raw/                  One .txt per monster (330 files)
  sections/             One .json per monster with raw string fields (330 files)
  monsters.json         Final monster output — array of 330 structured objects
  spells/
    raw_combined.txt    Full extracted spell text (debugging)
    raw/                One .txt per spell (339 files)
    sections/           One .json per spell with raw string fields (339 files)
  spells.json           Final spell output — array of 339 structured objects
  magic_items.json      (not yet built — stub pipeline)
  feats.json            (not yet built — stub pipeline)
  classes.json          (not yet built — stub pipeline)
  species.json          (not yet built — stub pipeline)
  origins.json          (not yet built — stub pipeline)
```

---

## Monster pipeline

### SRD 5.2.1 format (differs from 5.1 — important)
- `AC 17 Initiative +7 (17)` — AC and Initiative on the same line
- `HP 150 (20d10 + 40)` — "HP" prefix not "Hit Points"
- `CR 10 (XP 5,900, or 7,200 in lair; PB +4)` — "CR" not "Challenge"; includes PB
- Ability score table embeds saving throws: `Str 30 +10 +10` = score, modifier, save
- `Immunities` field unifies damage and condition immunities (semicolon separates them)
- `Resistances` / `Vulnerabilities` are standalone fields
- `Traits` is an explicit section header (between stats and Actions)
- `Bonus Actions` is an explicit section header (new in 5.2.1)
- Attack format: `Melee Attack Roll: +9, reach 15 ft.` (no "to hit", no "Weapon/Spell" subtype)

### Monster section page range
Pages 258–364 (all remaining pages of the PDF after 257).
- Pages 258–343: main monster entries
- Pages 344–364: Appendix beasts (dinosaurs, animals, etc.)

### Key technical decisions

**PDF extraction (srd/phases/raw.py)**
- **pdfplumber** chosen over pypdf/pdfminer for word-level x/y coordinates enabling two-column reading order.
- Column split detected dynamically (largest horizontal gap near page midpoint ±30%), not hardcoded.
- Page footers stripped; hyphenated line breaks rejoined.
- Monster boundaries detected via size/type/alignment meta line regex, walking back to name.
- `SIZES` regex handles compound sizes: `(?:Tiny|...|Gargantuan)(?:\s+or\s+(?:Tiny|...|Gargantuan))?`
- `--split-only` flag: re-splits existing `raw_combined.txt` without re-reading the PDF.

**Entry parsing (srd/phases/structured.py — parse_named_blocks)**
- Line-based approach (not lookahead regex): new entry only when `Name. Description...` has text on same line.
- `_INVALID_NAME_RE` rejects names ending in damage type words, "(level N version)", "Hit Points".
- `_USES_RE` handles `(2/Day)`, `(3/Day, or 4/Day in Lair)`, `(3/Day Each)`.

**Ability scores (srd/phases/sections.py)**
- Table: score + modifier + save per stat; extraction order varies by column position.
- Normalized Unicode minus (−); regex `(\d+)\s+([+\-]\d+)\s+([+\-]?\d+)` with optional save sign.
- Stats assigned in canonical order: str, dex, con, int, wis, cha.

### Monster JSON structure (per object)
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
    "dex": {"score": 9}
  },
  "skills": {"history": "expert", "perception": "expert"},
  "damage_vulnerabilities": [],
  "damage_resistances": [],
  "damage_immunities": [],
  "condition_immunities": [],
  "senses": {"darkvision": 120},
  "languages": ["Deep Speech", "telepathy 120 ft."],
  "challenge": {"rating": "10", "xp": 5900, "xp_lair": 7200},
  "special_abilities": [{"name": "Amphibious", "description": "..."}],
  "actions": [
    {
      "name": "Tentacle",
      "description": "...",
      "attack": {"type": "melee_weapon_attack", "bonus": 9, "reach": 15},
      "damage": [{"dice_count": 2, "dice_type": 6, "modifier": 5, "damage_type": "bludgeoning"}],
      "save": {"dc": 14, "stat": "con"}
    }
  ],
  "bonus_actions": [],
  "reactions": [],
  "legendary_actions": {"description": "...", "uses": 3, "uses_lair": 4, "actions": [...]},
  "lair_actions": [],
  "variant_of": "Black Dragon"
}
```
`variant_of` omitted when no mapping exists. 57/330 monsters have it.

### Monster computed fields (not in JSON — use helpers.py)
- `ability_modifier(score)` → `floor((score - 10) / 2)`
- `hp_modifier(con_score, dice_count)` → ability_modifier(con) × dice_count
- `proficiency_bonus(cr_rating)` → standard 5e CR→PB lookup
- `initiative_score(initiative_bonus)` → `10 + initiative_bonus`
- `hp_average / hp_formula` — uses hp_modifier internally
- `saving_throw(score, pb, proficiency=None)` — pass `save_proficiency` key value
- `skill_bonus(stat_score, pb, proficiency)`
- `passive_perception(wis_score, pb, proficiency=None)`
- `damage_average / damage_formula`

### Monster known issues
- **Lair actions**: `lair_actions: []` for all — confirmed N/A in SRD 5.2.1.
- **Spellcasting**: 41 monsters have structured spellcasting (via `parse_spellcasting()`). Non-standard entries (Hellfire Spellcasting, Spell Storing) left as plain strings.
- **Multiattack**: 154/155 have `attack_pattern`. Hydra (variable count) is intentional exception.
- **SRD typos**: See `srd_bugs.md` — 5 discrepancies across 4 monsters (all confirmed SRD anomalies or typos).

---

## Spell pipeline

### Spell section page range
Pages 107–175 of the PDF ("Spell Descriptions" chapter).

### Key technical decisions

**Font-aware SC700 extraction (spells/phases/raw.py)**
Spell names use `GillSans-SemiBold-SC700` small-caps font. Regular word-based extraction
garbles them because initial capitals (size 12pt) and small-cap letters (size 8.4pt) sit at
slightly different y-positions. Fix: two-pass char-level extraction per column:
- Pass 1: collect SC700 chars, group into rows with Y_TOL=8, lowercase size<10 uppercase chars → clean spell name
- Pass 2: collect non-SC700 body chars, excluding SC700 y-ranges (±2pt tolerance) → body text
- Sort body chars by exact `(top, x0)` — NOT quantized; quantizing puts chars from adjacent lines in the same sort bucket, causing interleaving and per-char "rows"
- `_BODY_Y_TOL = 2`: keeps inline bold-italic headers ("Cantrip Upgrade.", "Using a Higher-Level Spell Slot.") on separate rows from body text (they sit 2.4–4pt below)

**Spell boundary splitting (spells/phases/raw.py — split_into_spells)**
- Find every line matching the level/cantrip meta pattern
- Walk back to find spell name using `_is_valid_spell_name()` (filters artifact lines)
- Block extends from name line to next spell's meta line; all lines == next_name filtered out
  (handles carry-over copies of the next spell's name from two-column layout)

**Section parsing (spells/phases/sections.py)**

Labeled fields (Casting Time, Range, Components, Duration) are parsed in two modes:
1. **Happy path**: all four fields appear as `Label: value` on one line — primary regex `^Label:[ \t]*(.+)$` (note `[ \t]*`, not `\s*` — avoids crossing newlines)
2. **Fallback** (Chill Touch page 115 — Cambria-Bold labels on separate lines): a queue-based parser collects labels and values in order, then pairs them FIFO. The PDF layout interleaves them: L1, L2, V1, L3, V2, L4, V3, V4.

Both modes also handle:
- `Component:` (singular) vs `Components:` (plural) — pattern uses `Components?:`
- Multi-line casting times (Reaction/Bonus Action spells): continuation lines between Casting Time and Range are joined
- `_split_at_inline_header()`: splits description at "Cantrip Upgrade." or "Using a Higher-Level Spell Slot." headers; lowercase-starting lines after the header are re-appended to the main description (PDF layout artifact)
- Embedded stat blocks detected via `CREATURE_META_RE` in both description and higher_level sections

**Spell corrections (data/spell_corrections.json)**
- `false_life`: "Using a Higher-Level Spell Slot." appeared before the description in raw text (PDF layout); corrected fields provided directly.

### Spell JSON structure (per object)
```json
{
  "slug": "fireball",
  "name": "Fireball",
  "level": 3,
  "school": "Evocation",
  "classes": ["Sorcerer", "Wizard"],
  "ritual": false,
  "casting_time": "Action",
  "range": "150 feet",
  "verbal": true,
  "somatic": true,
  "material": true,
  "material_desc": "a ball of bat guano and sulfur",
  "concentration": false,
  "duration": "Instantaneous",
  "description": "A bright streak flashes from you...",
  "higher_level": "The damage increases by 1d6 for each spell slot level above 3.",
  "cantrip_upgrade": "",
  "embedded_stat_blocks": []
}
```
Fields present for all 339 spells. `higher_level` and `cantrip_upgrade` are `""` when absent.
`embedded_stat_blocks` is a list of raw strings (3 spells: Animate Objects, Giant Insect, Summon Dragon).

### Spell statistics
- 339 total spells
- Level distribution: 0→27, 1→57, 2→57, 3→42, 4→34, 5→38, 6→31, 7→20, 8→17, 9→16
- 109 spells have `higher_level` text; 9 have `cantrip_upgrade`
- 3 have embedded stat blocks (raw, not yet deep-parsed)

---

## Running the pipeline
```bash
# Full pipeline (all 21 phases — phases 1 and 4 re-read the PDF, ~2 min each)
python3 run_all.py

# Section-specific flags (only run one content type's phases)
python3 run_all.py --monsters        # phases 1–3
python3 run_all.py --spells          # phases 4–6
python3 run_all.py --magic-items     # phases 7–9   (stub — prints "not yet implemented")
python3 run_all.py --feats           # phases 10–12 (stub)
python3 run_all.py --classes         # phases 13–15 (stub)
python3 run_all.py --species         # phases 16–18 (stub)
python3 run_all.py --origins         # phases 19–21 (stub)

# Resume from a specific phase (skip PDF extraction)
python3 run_all.py --start 2   # monster sections + structured
python3 run_all.py --start 3   # monster structured only
python3 run_all.py --start 5   # spell sections + structured
python3 run_all.py --start 6   # spell structured only

# Combined viewer (monsters + spells + stub tabs for other content types)
python3 viewer.py              # → http://localhost:8080

# Verification
python3 verify.py              # monster proficiency-bonus check
```

## Stub pipeline pattern (for contributors)
Each new content type follows the same 3-phase pattern as monsters and spells.
To implement a stub, edit the 3 files in `{type}/phases/` and follow the same
conventions as `srd/phases/` (monsters) or `spells/phases/`:
1. `raw.py`        — extract text from PDF → `output/{type}/raw/<slug>.txt`
2. `sections.py`   — parse into labeled fields → `output/{type}/sections/<slug>.json`
3. `structured.py` — build final JSON → `output/{type}.json`

The viewer (`viewer.py`) will automatically display the data once the JSON file exists.
The HTTP handler already serves `/{type}.json` (returning `[]` until the file is built).
