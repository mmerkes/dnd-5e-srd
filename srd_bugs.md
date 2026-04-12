# SRD 5.2.1 Known Bugs and Typos

## Invisible Stalker — Initiative Score

- **Field**: `armor_class.initiative_score` (removed from JSON; computed via `helpers.initiative_score()`)
- **SRD value**: 22
- **Expected**: 17 (10 + initiative_bonus +7)
- **Note**: DEX 19 → +4 modifier; PB +3 → initiative bonus = +7; correct score = 17. The PDF shows 22, which matches no formula. Confirmed SRD typo. `helpers.initiative_score(7)` returns the correct value 17.

Discrepancies between the SRD PDF values and what the standard 5e formulae would produce.
Verified against `output/monsters.json` via `verify.py`.

---

## Adult Bronze Dragon — Spell Save DC

- **Field**: `Spellcasting` action → `spell_save_dc`
- **SRD value**: 17
- **Expected**: 18 (CHA 20 → +5 modifier; PB +5; 8 + 5 + 5 = 18)
- **Note**: Likely an SRD typo. Either the spell save DC should be 18, or CHA should be 19 (+4 → DC 17).

## Adult Bronze Dragon — Thunderclap Save DC

- **Field**: `Thunderclap` action (legendary) → `save.dc`
- **SRD value**: 17
- **Expected**: 18 (same formula as above)
- **Note**: Consistent with the spellcasting DC discrepancy above — both are 17 instead of 18.
  Either both are intentional (DC 17 is deliberate) or both share the same root typo (CHA should be 20).

## Ancient White Dragon — Freezing Burst Save DC

- **Field**: `Freezing Burst` legendary action → `save.dc`
- **SRD value**: 20
- **Expected**: 22 (CON 22 → +6 modifier; PB +6; 8 + 6 + 6 = 20... wait, STR 26 → +8, 8+8+6=22)
- **Note**: DC 20 matches 8 + CON modifier (+6) + PB (+6) = 20 using a +6 modifier, but the
  highest-modifier stat (STR 26 → +8) gives DC 22. The DC 20 appears intentionally lower —
  possibly using a fixed value rather than the formula.

## Sphinx of Valor — Weight of Years Save DC

- **Field**: `Weight of Years` legendary action → `save.dc`
- **SRD value**: 16
- **Expected**: 20 (WIS 20 → +5 modifier; PB +6; 8 + 5 + 6 = 19; or CHA 18 → +4, 8+4+6=18)
- **Note**: DC 16 is well below any formula result for this CR 17 creature. Appears to be a
  deliberate design choice to keep a status effect accessible, not a typo.

## Giant Frog — Stealth Skill

- **Field**: `skills.stealth` (stored as `"proficient"` via corrections.json)
- **SRD value**: +4
- **Expected**: +3 (DEX 13 → +1 modifier; PB +2; proficient = +3)
- **Note**: +4 is one above proficient, doesn't match expertise (+5). Likely an SRD off-by-one typo.

## Shambling Mound — Stealth Skill

- **Field**: `skills.stealth` (stored as `"proficient"` via corrections.json)
- **SRD value**: +3
- **Expected**: +2 (DEX 8 → -1 modifier; PB +3; proficient = +2)
- **Note**: +3 is one above proficient, doesn't match expertise (+5). Same pattern as Giant Frog — likely SRD off-by-one typo.

## Swarm of Ravens — Cacophony Save DC

- **Field**: `Cacophony` action → `save.dc`
- **SRD value**: 10
- **Expected**: 11+ (DEX 12 → +1 modifier; PB +2; 8 + 1 + 2 = 11)
- **Note**: DC 10 is one below the minimum formula result. Could be intentional (flat DC 10)
  or an off-by-one typo.

## Young White Dragon — INT Saving Throw (PDF rendering artifact) ✅ CORRECTED

- **Field**: `ability_scores.int.save_proficiency`
- **SRD PDF**: renders this save unsigned (no + or −), causing raw extraction of `2` instead of `-2`
- **Correct value**: −2 (INT 6 → −2 modifier, unproficient) — `save_proficiency` key should be absent
- **Fix**: `corrections.json` overrides `_saving_throw_raw` for Young White Dragon INT to `−2`
  before proficiency inference runs. The corrected value matches `mod(−2)` → unproficient → key absent.
- **verify.py**: not flagged
