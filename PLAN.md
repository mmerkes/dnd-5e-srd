# SRD Monster Parser — Future Work Plan

## Current state
- `output/monsters.json` contains 330 monsters, fully parsed.
- All core stat block fields are typed and structured.
- 41 monsters have fully structured spellcasting (Phase 4b complete).
- Multiattack entries have structured `attack_pattern` (Phase 4c complete).
- All derivable fields removed from JSON; `helpers.py` provides the full set of computed helpers (see CONTEXT.md Computed Fields section). Removed: `ability_scores.*.modifier`, `hit_points.modifier`, `hit_points.average`, `hit_points.formula`, `armor_class.initiative_score`, `challenge.proficiency_bonus`, `skills.*` (flat bonuses → proficiency enums), `senses.passive_perception`, `damage.average`, `damage.formula`.
- `verify.py` runs proficiency-bonus verification; **5 discrepancies across 4 monsters** — all known SRD anomalies (Phase 5a complete).
- Phase 1 cross-contamination fixed: `SIZES` regex now handles "Medium or Small" pattern.
  All 330 boundaries detected; all 5 lycanthropes (including Wereboar) and all NPC archetypes present.
- `srd_bugs.md` tracks confirmed SRD typos and non-standard DCs.
- `viewer.py` provides a local web UI for browsing and auditing stat blocks (Phase 5d complete).
- `uses_per_day` field on actions stores a dict `{"uses": N, ["uses_lair": M], ["each": true]}`.
- See `CONTEXT.md` for architecture details and known issues.

---

## Phase 4 — Fix known parsing gaps

These are improvements to the existing three scripts, not new features.

### 4a. Lair actions ✅ RESOLVED — NOT APPLICABLE
Investigation confirmed: SRD 5.2.1 does NOT include separate lair action stat
blocks. Lair info appears only as modifiers on legendary resistance uses and
legendary action use counts. `lair_actions: []` is correct for all monsters.

### 4b. Spellcasting action sub-structure ✅ DONE
`parse_spellcasting()` added to `parse_structured.py`. Called from
`parse_named_blocks()` for any entry whose name contains "spellcasting".
41 monsters now have structured spellcasting fields alongside `description`.
Non-standard entries (Hellfire Spellcasting, Spell Storing) are unaffected.
Handles: no At Will section, no spell save DC, commas inside spell parens,
multiple per-day tiers (1/Day, 2/Day, 1/Day Each, etc.).

### 4c. Multiattack sub-structure
The Multiattack description currently stores everything as a string. Parse the attack
pattern into structured data:
```json
{
  "name": "Multiattack",
  "attack_pattern": [
    {"action": "Rend", "count": 3},
    {"action": "Fire Breath", "count": 1, "optional": true}
  ]
}
```
This requires recognizing patterns like "makes N X attacks", "can replace one attack with Y", etc.

✅ DONE — `parse_multiattack()` added to `parse_structured.py`. 154/155 Multiattack
entries now have `attack_pattern`. Hydra (variable head count) is the only intentional
exception. Also fixed a `_CONTINUATION_DESC_RE` filter that was causing three monsters
(Oni, Salamander, Shambling Mound) to have truncated Multiattack descriptions due to
PDF line-wrap producing false header lines like "Ray attacks. It can replace…".

Handles: simple N X attacks, fixed multi-attack combos, any-combination attacks,
optional replacements (single and A/B choice), bundled uses (including ", uses X twice"),
and "or it makes N Y attacks" alternatives.

### 4d. Computed modifiers ✅ DONE
- `ability_scores.*.modifier` removed from JSON output.
- `hit_points.modifier` removed from JSON output (formula string retains the +N value).
- `helpers.py` created with `ability_modifier(score)` and `hp_modifier(con_score, dice_count)`.
- `parse_structured.py` no longer imports `math`; updated docstrings reference helpers.

---

## Phase 5 — Data enrichment

Features that add value on top of the existing JSON without changing the schema.

### 5a. Proficiency bonus verification ✅ DONE
`verify.py` checks attack bonuses, save DCs, spell attack bonuses, spell save DCs,
and ability saving throws against the standard 5e formulae.

Initial results (before Phase 1 fix): 34 discrepancies across 19 monsters.
Current results (after Phase 1 fix + saving throw refactor): **5 discrepancies across 4 monsters**
— all intentional SRD action DCs. Young White Dragon INT corrected via `corrections.json`.
Details in `srd_bugs.md`.

**Category A — Phase 1 cross-contamination (14 monsters) ✅ FIXED:**
Root cause: `SIZES` regex only matched single size words; "Medium or Small" (used by all
NPC archetypes and lycanthropes) was never detected as a boundary. Fixed by updating `SIZES`
to `(?:Tiny|...|Gargantuan)(?:\s+or\s+(?:Tiny|...|Gargantuan))?`. Monster count rose
from 294 → 330. All 14 contaminated monsters are now clean.

**Category B — Intentional non-standard DCs (4 instances across 4 monsters):**
Some legendary/recharge action DCs are intentionally lower than what the formula
would produce (deliberate SRD design choice, not parser errors):
Ancient White Dragon Freezing Burst (DC 20 vs expected 22),
Sphinx of Valor Weight of Years (DC 16 vs expected 20),
Swarm of Ravens Cacophony (DC 10 vs expected 11+),
Adult Bronze Dragon Thunderclap (DC 17 vs expected 18 — possible SRD typo).

**Category C — Adult Bronze Dragon spell save DC (1 instance):**
Spell save DC in the Spellcasting block is 17, but CHA 20 (+5) + PB +5 = 18.
The DC 17 is verbatim from the SRD PDF — either an SRD typo or CHA should be 19.

**Category D — Young White Dragon INT saving throw (1 instance):**
INT saving throw stored as +2; expected -2 (unproficient) or +1 (proficient, PB+3).
Pre-existing issue: PDF renders this save unsigned, parsed as +2 instead of -2.

### 5b. Variant tagging ✅ DONE
`variant_mapping.json` maps 57 monsters to their base creature. Loaded by `parse_structured.py`
at module level; `variant_of` field added only when a mapping exists. Categories covered:
dragon age-stages (40 entries across 10 colors), undead templates (Ogre Zombie, Minotaur Skeleton,
Warhorse Skeleton), rank/boss variants (Bandit/Guard/Hobgoblin/Goblin/Pirate Captains, Tough Boss,
Warrior Veteran, Priest Acolyte, Cultist Fanatic), and named monster variants
(Vampire Spawn, Vampire Familiar, Mummy Lord, Troll Limb).

### 5c. Source tagging ✅ DONE
`"source": "SRD 5.2.1"` added to every monster object via `build_monster()` in `parse_structured.py`.

### 5d. Stat block viewer ✅ DONE
`viewer.py` — stdlib-only Python HTTP server, no external dependencies.
Usage: `python3 viewer.py [port]` → http://localhost:8080

Features:
- Sidebar: name search, type and CR filters, monster list with CR badges
- Keyboard arrow navigation through the filtered list
- Stat block styled after the D&D parchment aesthetic, with all computed values
  rendered client-side (HP average, initiative score, passive perception, skill
  bonuses, proficiency bonus, saving throws) — mirrors helpers.py in JS
- Collapsible raw JSON panel at the bottom of each stat block

---

## Phase 6 — API / consumption layer

Build a way to use `monsters.json` programmatically beyond raw JSON reads.

### 6a. TypeScript types
Generate or write TypeScript interfaces that match the JSON structure:
```typescript
interface Monster {
  name: string;
  size: Size;
  type: CreatureType;
  armor_class: ArmorClass;
  hit_points: HitPoints;
  ability_scores: AbilityScores;
  // ...
}
```
This makes the data usable in a frontend app with full type safety.

### 6b. SQLite loader
Write a script (`load_db.py` or `load_db.ts`) that loads `monsters.json` into a SQLite
database with normalized tables:
- `monsters` — core fields
- `monster_actions` — one row per action/bonus action/reaction
- `monster_damage_rolls` — one row per damage roll
- `monster_ability_scores` — one row per stat
This enables SQL queries like "find all CR 5-10 undead with darkvision > 60ft".

### 6c. REST API (optional)
Wrap the SQLite DB in a small FastAPI (Python) or Express (TypeScript) server for use by
other tools or a web UI.

---

## Phase 7 — Extend to other SRD sections

The PDF has other structured content worth parsing with the same pipeline approach.

### 7a. Spells (estimated pages 125–200)
Similar pipeline: raw extraction → section labeling → structured JSON.
Key fields: name, level, school, casting_time, range, components, duration, description,
higher_levels, classes.

### 7b. Magic Items
Key fields: name, type, rarity, attunement, description.

### 7c. Classes and features
More complex — nested structure with subclass variants.

---

## Suggested next session start

1. Read `CONTEXT.md` and `PLAN.md`
2. Run `python3 run_all.py --start 3` to confirm clean output (phases 1 and 2 are stable)
3. Run `python3 verify.py` to confirm 5 discrepancies across 4 monsters (all known SRD anomalies)
4. Pick up at Phase 6 (TypeScript types or SQLite loader) or Phase 7 (Spells parser)

## Running individual phases
```bash
python3 -m srd.phases.raw            # ~2 min, only needed if PDF or pages change
python3 -m srd.phases.sections       # fast, re-run when section detection changes
python3 -m srd.phases.structured     # fast, re-run when field parsers change
python3 run_all.py --start 2         # skip PDF extraction, run sections + structured
python3 run_all.py --start 3         # only re-run the final structuring step
```
