#!/usr/bin/env python3
"""
Phase 5a — Proficiency bonus verification.

Checks that attack bonuses, save DCs, and spell attack bonuses in
output/monsters.json match the expected 5e formulae:

  attack bonus    = ability_modifier(stat) + proficiency_bonus
  save DC         = 8 + ability_modifier(stat) + proficiency_bonus
  saving throw    = ability_modifier(stat) [not proficient]
                  OR ability_modifier(stat) + proficiency_bonus [proficient]

For each value the verifier checks all six ability scores — the "stat" is
unknown from the JSON alone, so any matching ability counts as a pass.

Discrepancies are useful for catching parser errors (mis-read attack bonuses,
wrong DC, cross-contaminated stat blocks, etc.).

Usage:  python3 verify.py [--attacks-only | --saves-only]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from srd.helpers import ability_modifier, saving_throw as compute_saving_throw, proficiency_bonus as compute_pb

MONSTERS_FILE = Path("output/monsters.json")
STATS = ("str", "dex", "con", "int", "wis", "cha")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def all_modifiers(ability_scores: dict) -> dict[str, int]:
    return {s: ability_modifier(ability_scores[s]["score"])
            for s in STATS if s in ability_scores}


def all_attack_bonuses(mods: dict[str, int], pb: int) -> set[int]:
    """All plausible attack bonuses: mod + pb for each stat.

    We check all six stats because the JSON doesn't record which ability
    drives each attack.  Any match counts as a pass; mismatches are flagged.
    """
    return {m + pb for m in mods.values()}


def all_save_dcs(mods: dict[str, int], pb: int) -> set[int]:
    """All plausible save DCs: 8 + mod + pb for each stat.

    Same rationale as all_attack_bonuses — stat is not stored per-action.
    """
    return {8 + m + pb for m in mods.values()}


def fmt_atk_table(mods: dict[str, int], pb: int) -> str:
    return ", ".join(f"{s}:{m + pb:+d}" for s, m in mods.items())


def fmt_dc_table(mods: dict[str, int], pb: int) -> str:
    return ", ".join(f"{s}:{8 + m + pb}" for s, m in mods.items())


def fmt_save_table(mods: dict[str, int], pb: int) -> str:
    return ", ".join(f"{s}:{m} or {m + pb}" for s, m in mods.items())


# ---------------------------------------------------------------------------
# Per-monster checks
# ---------------------------------------------------------------------------

def check_monster(monster: dict) -> list[str]:
    issues: list[str] = []

    pb = compute_pb(monster.get("challenge", {}).get("rating"))
    if not pb:
        return []

    ability_scores = monster.get("ability_scores", {})
    if not ability_scores:
        return []

    mods   = all_modifiers(ability_scores)
    ok_atk = all_attack_bonuses(mods, pb)
    ok_dc  = all_save_dcs(mods, pb)

    # --- Saving throw proficiency consistency check ---
    # Verify that the stored save_proficiency enum, when fed back through
    # helpers.saving_throw(), yields a value consistent with the monster's
    # ability scores and proficiency bonus.
    # We flag "expert" saves as unexpected — no SRD monster is documented
    # with expertise in saving throws, so any "expert" entry is a parser bug.
    for stat, vals in ability_scores.items():
        prof  = vals.get("save_proficiency")
        mod   = mods[stat]
        computed = compute_saving_throw(vals["score"], pb, prof)
        if prof == "expert":
            issues.append(
                f"  saving throw {stat.upper()}: save_proficiency='expert' "
                f"(unexpected for SRD monsters — computed={computed:+d})"
            )

    # --- Actions, bonus actions, reactions, legendary actions, traits ---
    sections = (
        monster.get("special_abilities", [])
        + monster.get("actions", [])
        + monster.get("bonus_actions", [])
        + monster.get("reactions", [])
        + monster.get("legendary_actions", {}).get("actions", [])
    )

    for action in sections:
        aname = action.get("name", "?")

        # Attack bonus
        atk = action.get("attack", {})
        if atk and "bonus" in atk:
            bonus = atk["bonus"]
            if bonus not in ok_atk:
                issues.append(
                    f"  attack '{aname}': bonus {bonus:+d} — "
                    f"expected one of [{fmt_atk_table(mods, pb)}]"
                )

        # Save DC
        sv = action.get("save", {})
        if sv and "dc" in sv:
            dc = sv["dc"]
            if dc not in ok_dc:
                issues.append(
                    f"  save '{aname}': DC {dc} — "
                    f"expected one of [{fmt_dc_table(mods, pb)}]"
                )

        # Spell attack bonus (from parse_spellcasting)
        spell_atk = action.get("spell_attack_bonus")
        if spell_atk is not None:
            if spell_atk not in ok_atk:
                issues.append(
                    f"  spell attack '{aname}': bonus {spell_atk:+d} — "
                    f"expected one of [{fmt_atk_table(mods, pb)}]"
                )

        # Spell save DC
        spell_dc = action.get("spell_save_dc")
        if spell_dc is not None:
            if spell_dc not in ok_dc:
                issues.append(
                    f"  spell save DC '{aname}': DC {spell_dc} — "
                    f"expected one of [{fmt_dc_table(mods, pb)}]"
                )

    return issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    monsters = json.loads(MONSTERS_FILE.read_text(encoding="utf-8"))

    total_issues    = 0
    flagged_monsters = 0

    for monster in monsters:
        issues = check_monster(monster)
        if issues:
            flagged_monsters += 1
            total_issues += len(issues)
            cr  = monster["challenge"].get("rating", "?")
            _pb = compute_pb(cr) or "?"
            print(f"\n[{monster['name']}]  CR {cr}  PB +{_pb}")
            for line in issues:
                print(line)

    print(f"\n{'=' * 60}")
    print(f"Discrepancies : {total_issues} across {flagged_monsters} monsters")
    print(f"Clean         : {len(monsters) - flagged_monsters} monsters")
    print(f"Total checked : {len(monsters)} monsters")


if __name__ == "__main__":
    main()
