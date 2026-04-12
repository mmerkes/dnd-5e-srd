# SRD Monster Parser — Session Context

## What this project does
Parses D&D 5e SRD 5.2.1 monster stat blocks from `SRD_CC_v5.2.1.pdf` into structured JSON.
Final output: `output/monsters.json` — 330 monsters, all fields typed and parsed.

## File structure
```
srd/
  __init__.py
  helpers.py            Computed-field utilities: ability_modifier(), hp_modifier(), etc.
  phases/
    __init__.py
    raw.py              Phase 1 — PDF extraction → output/raw/<slug>.txt
    sections.py         Phase 2 — Section labeling → output/sections/<slug>.json
    structured.py       Phase 3 — Deep parsing → output/monsters.json
data/
  variant_mapping.json  Manual variant_of mappings (57 entries) loaded by structured.py
  corrections.json      Manual corrections for PDF rendering artifacts (e.g. unsigned saving throws)
run_all.py            Convenience runner (supports --start 2 or --start 3 to resume)
verify.py             Phase 5a proficiency-bonus checker; reports SRD discrepancies
viewer.py             Stat block web viewer — python3 viewer.py → http://localhost:8080
srd_bugs.md           Confirmed SRD typos and non-standard values
requirements.txt      pdfplumber>=0.10.0
output/
  raw_combined.txt    Full extracted text (debugging)
  raw/                One .txt per monster (330 files)
  sections/           One .json per monster with raw string fields (330 files)
  monsters.json       Final output — array of 330 structured monster objects
```

## SRD 5.2.1 format (differs from 5.1 — important)
The PDF uses a newer stat block format. Key differences from the commonly documented 5.1 format:
- `AC 17 Initiative +7 (17)` — AC and Initiative on the same line
- `HP 150 (20d10 + 40)` — "HP" prefix not "Hit Points"
- `CR 10 (XP 5,900, or 7,200 in lair; PB +4)` — "CR" not "Challenge"; includes PB
- Ability score table now embeds saving throws: `Str 30 +10 +10` = score, modifier, save
- `Immunities` field unifies damage and condition immunities (semicolon separates them)
- `Resistances` / `Vulnerabilities` are standalone fields
- `Traits` is an explicit section header (between stats and Actions)
- `Bonus Actions` is an explicit section header (new in 5.2.1)
- Attack format: `Melee Attack Roll: +9, reach 15 ft.` (no "to hit", no "Weapon/Spell" subtype)

## Monster section page range
Pages 258–364 (all remaining pages of the PDF after 257).
- Pages 258–343: main monster entries
- Pages 344–364: Appendix beasts (dinosaurs, animals, etc.)
Initial estimate of 343 was wrong; extending to 364 added ~96 more monsters.

## Key technical decisions

### PDF extraction (parse_raw.py)
- **pdfplumber** chosen over pypdf/pdfminer because it gives word-level x/y coordinates,
  enabling correct two-column reading order reconstruction.
- Column split is detected dynamically by finding the largest horizontal gap in word coverage
  near the page midpoint (±30%), not hardcoded pixel offsets.
- Page footers (`"NNN System Reference Document 5.2.1"`) are stripped as a post-processing step.
- Hyphenated line breaks (`"Scorch-\ning"`) are rejoined before saving raw files.
- Monster boundaries are detected via a regex matching the distinctive size/type/alignment
  meta line (e.g. "Large Aberration, Lawful Evil"), then walking back to the name.
- `SIZES` regex handles compound sizes: `(?:Tiny|...|Gargantuan)(?:\s+or\s+(?:Tiny|...|Gargantuan))?`
  — required for NPC archetypes and lycanthropes which use "Medium or Small" as their size.
- **PDF column artifact fix**: some monster names appear twice in extracted text — once as
  a column artifact at the bottom of the previous page, once as the real entry start. Fixed by
  scanning the current block for the first occurrence of the next monster's name and trimming there.
- `--split-only` flag: re-splits existing `raw_combined.txt` without re-reading the PDF (fast).

### Entry parsing (parse_structured.py — parse_named_blocks)
- Uses a **line-based approach**, not a lookahead regex.
- A new entry starts only when a line matches `Name. Description...` with description text
  on the SAME line. This prevents bare continuation lines like `"Bludgeoning damage."` or
  `"Scorching Ray (level 3 version)."` from being mistaken for entry starts.
- Invalid name filter (`_INVALID_NAME_RE`) rejects names ending in damage type words
  (acid, fire, slashing, etc.), names containing "(level N version)", and "Hit Points".
- `_USES_RE` handles `"(2/Day)"`, `"(3/Day, or 4/Day in Lair)"`, and `"(3/Day Each)"`.

### Ability scores (parse_sections.py — parse_ability_scores)
- The 5.2.1 table format has score + modifier + save per stat.
- Text extraction produces inconsistent ordering (sometimes `Str 30 +10 +10`,
  sometimes `30 +10 +10 Str`) depending on PDF column positions.
- Fixed by normalizing Unicode minus (−), then using `re.findall(r"(\d+)\s+([+\-]\d+)\s+([+\-]?\d+)")`.
  The save sign is optional (`?`) because one monster (Young White Dragon) had an unsigned save
  extracted due to PDF rendering.
- Stats are assigned in canonical order: str, dex, con, int, wis, cha.
- Saving throw bonuses from this table replace the old "Saving Throws" labeled field.

### Damage rolls
- `average` and `formula` are intentionally omitted — use `helpers.damage_average()` and
  `helpers.damage_formula()` to compute at query time.
- `modifier` is stored because it is NOT always derivable as `attack.bonus - pb`:
  some spell/special attacks (e.g. Hurl Flame, Storm Bolt, Fiery Bolt) intentionally carry
  `modifier = 0` even though the attack roll includes the ability modifier. This is a
  deliberate SRD design choice, not a parser error.
- Flat damage (e.g. `"1 piercing damage"`) is stored as `dice_count=0, dice_type=0, modifier=N`.
- Secondary damage rolls (extra elemental damage on a hit) can have either `modifier = 0`
  or a non-zero modifier matching the primary ability.

### Immunities splitting
- SRD 5.2.1 uses a single `Immunities` field with a semicolon separator:
  `"Poison; Exhaustion, Poisoned"` → damage: ["Poison"], conditions: ["Exhaustion", "Poisoned"]
- When no semicolon, each item is classified against a known conditions set.

## Output JSON structure (per monster)
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
    "...": "..."
  },
  "skills": {"history": "expert", "perception": "expert"},
  "damage_vulnerabilities": [],
  "damage_resistances": [],
  "damage_immunities": [],
  "condition_immunities": [],
  "senses": {"darkvision": 120},
  "languages": ["Deep Speech", "telepathy 120 ft."],
  "challenge": {"rating": "10", "xp": 5900, "xp_lair": 7200},
  "special_abilities": [
    {"name": "Amphibious", "description": "..."}
  ],
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
`variant_of` is omitted entirely when the monster has no mapping in `variant_mapping.json`.
57 out of 330 monsters have this field.

## Computed fields (not in JSON)
These values are derivable from other stored fields and are intentionally excluded
from the JSON output. Use `helpers.py` to compute them at query time:
- `ability_modifier(score)` → `floor((score - 10) / 2)` — ability score modifier
- `hp_modifier(con_score, dice_count)` → `ability_modifier(con_score) * dice_count`
  — the flat bonus in the HP dice formula (e.g., +40 in "20d10+40")
- `proficiency_bonus(cr_rating)` → standard 5e CR→PB lookup (CR 0–4 = +2, 5–8 = +3, … 29–30 = +9)
- `initiative_score(initiative_bonus)` → `10 + initiative_bonus`
- `hp_average(dice_count, dice_type, con_score)` → expected average HP (uses `hp_modifier` internally)
- `hp_formula(dice_count, dice_type, con_score)` → e.g. `"20d10+40"` (uses `hp_modifier` internally)
- `saving_throw(score, pb, proficiency=None)` → ability modifier [+ pb if proficient] [+ 2×pb if expert]
  — pass `ability_scores[stat]["save_proficiency"]` (key absent = unproficient)
- `skill_bonus(stat_score, pb, proficiency)` → bonus for a listed skill (`"proficient"` or `"expert"`)
- `passive_perception(wis_score, pb, proficiency=None)` → `10 + wis_mod [+ pb] [+ 2×pb]`
  — pass `skills.get("perception")`; `None` = perception not listed (unproficient)
- `damage_average(dice_count, dice_type, modifier)` → expected average damage; flat when `dice_count == 0`
- `damage_formula(dice_count, dice_type, modifier)` → e.g. `"2d6+5"`, `"2d8"`, `"1"` (flat)

## uses_per_day structure (per-action field)
Some special abilities and actions have a daily-use limit indicated by a "(N/Day)" parenthetical.
These are stored as a dict (not a flat int) to preserve lair variants and "each" flags:
```json
{"uses": 3}
{"uses": 3, "uses_lair": 4}
{"uses": 3, "each": true}
```
Example: `"Legendary Resistance (3/Day, or 4/Day in Lair)"` → `uses_per_day: {"uses": 3, "uses_lair": 4}`.
Note: the legendary_actions section uses a separate top-level `uses`/`uses_lair` on the
`legendary_actions` object itself (not per-action).

## Known remaining issues / edge cases
- **Lair actions**: 0 monsters have lair_actions parsed. Confirmed N/A — SRD 5.2.1 does not
  include separate lair action stat blocks. `lair_actions: []` is correct for all monsters.
- **Spellcasting actions**: Parsed into structured sub-fields (`spellcasting_ability`,
  `spell_save_dc`, `spell_attack_bonus`, `spells.at_will`, `spells.per_day`) via
  `parse_spellcasting()` in `parse_structured.py`. 41 monsters have this structure.
  Non-standard entries (Pit Fiend's `Hellfire Spellcasting`, Shield Guardian's
  `Spell Storing`) are skipped and left as plain description strings.
- **Multiattack descriptions**: Parsed into `attack_pattern` list via `parse_multiattack()`
  in `parse_structured.py`. Hydra (variable count) is the only intentional exception.
  Patterns handled: simple N-X, fixed combos, any-combination, optional replacements,
  A/B choice pairs, bundled uses (including twice), or-it-makes alternatives.
- **Legendary Resistance**: Appears as a special_ability rather than a dedicated field.
  Uses-per-day and lair variant are captured via `uses_per_day` key.
- **Some descriptions contain residual formatting artifacts** from hyphenated PDF line breaks
  that aren't caught by the `"(\w)-\n(\w)"` pattern (e.g. mid-vowel splits).
- **SRD typos/non-standard values**: See `srd_bugs.md` for the 6 confirmed discrepancies
  (Adult Bronze Dragon DC 17 spell save, Ancient White Dragon Freezing Burst DC 20,
  Sphinx of Valor Weight of Years DC 16, Swarm of Ravens Cacophony DC 10,
  Young White Dragon INT saving throw +2 instead of -2).
