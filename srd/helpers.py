"""
Shared utility functions for the SRD 5.2.1 monster data.

These implement calculations that are purely derived from other stored fields
and therefore intentionally omitted from the JSON output.  Import this module
whenever you need to compute them from the JSON at query time.
"""

from __future__ import annotations

import math


def ability_modifier(score: int) -> int:
    """
    Standard 5e ability score modifier: floor((score - 10) / 2).

    Examples:
        ability_modifier(10) == 0
        ability_modifier(21) == 5
        ability_modifier(9)  == -1
    """
    return math.floor((score - 10) / 2)


def hp_modifier(con_score: int, dice_count: int) -> int:
    """
    Flat HP bonus in a monster's hit-point formula.

    Equals CON modifier × dice_count (one CON modifier per Hit Die).
    This value appears as the +N in formulas like "20d10+40".

    Examples:
        hp_modifier(15, 20) == 40   # CON 15 → +2 modifier, 20 HD → +40
        hp_modifier(10, 8)  == 0    # CON 10 → +0 modifier
        hp_modifier(9, 4)   == -4   # CON 9  → -1 modifier, 4 HD → -4
    """
    return ability_modifier(con_score) * dice_count


_CR_TO_PB: dict[str, int] = {
    "0": 2, "1/8": 2, "1/4": 2, "1/2": 2,
    "1": 2, "2": 2, "3": 2, "4": 2,
    "5": 3, "6": 3, "7": 3, "8": 3,
    "9": 4, "10": 4, "11": 4, "12": 4,
    "13": 5, "14": 5, "15": 5, "16": 5,
    "17": 6, "18": 6, "19": 6, "20": 6,
    "21": 7, "22": 7, "23": 7, "24": 7,
    "25": 8, "26": 8, "27": 8, "28": 8,
    "29": 9, "30": 9,
}


def proficiency_bonus(cr_rating: str | None) -> int | None:
    """
    Standard 5e proficiency bonus for a given CR rating string.

    Examples:
        proficiency_bonus("10")  == 4
        proficiency_bonus("1/4") == 2
        proficiency_bonus("0")   == 2
    """
    if cr_rating is None:
        return None
    return _CR_TO_PB.get(str(cr_rating))


def initiative_score(initiative_bonus: int) -> int:
    """
    Initiative score (the value shown in parentheses on the stat block).
    Always 10 + initiative_bonus per the 5e 2024 rules.

    Note: The Invisible Stalker's SRD stat block shows 22 instead of the
    correct 17 — that is a confirmed SRD typo. helpers.initiative_score()
    returns the correct value.

    Example:
        initiative_score(7) == 17
    """
    return 10 + initiative_bonus


def hp_average(dice_count: int, dice_type: int, con_score: int) -> int:
    """
    Expected average hit points.

    Equivalent to damage_average(dice_count, dice_type, hp_modifier(con_score, dice_count)).

    Examples:
        hp_average(20, 10, 15) == 150   # 20d10, CON 15 → +2 mod → +40 → avg 150
        hp_average(6, 8, 10)   == 27    # 6d8, CON 10 → +0 mod → avg 27
    """
    return damage_average(dice_count, dice_type, hp_modifier(con_score, dice_count))


def hp_formula(dice_count: int, dice_type: int, con_score: int) -> str:
    """
    Hit point formula string, e.g. "20d10+40".

    Equivalent to damage_formula(dice_count, dice_type, hp_modifier(con_score, dice_count)).

    Examples:
        hp_formula(20, 10, 15) == "20d10+40"
        hp_formula(6, 8, 10)   == "6d8"
        hp_formula(4, 6, 8)    == "4d6-4"   # CON 8 → -1 mod
    """
    return damage_formula(dice_count, dice_type, hp_modifier(con_score, dice_count))


def skill_bonus(stat_score: int, pb: int, proficiency: str) -> int:
    """
    Skill check bonus for a listed skill.

    Call this only for skills that appear in monster["skills"] — listed skills
    are always at least proficient in 5e.  Pass the dict value directly.

    proficiency values (from the skills dict in monsters.json):
      "proficient"  →  ability modifier + pb
      "expert"      →  ability modifier + 2 × pb

    Examples:
        skill_bonus(14, 3, "proficient")  == 5
        skill_bonus(14, 3, "expert")      == 8
    """
    mod = ability_modifier(stat_score)
    if proficiency == "expert":
        return mod + 2 * pb
    return mod + pb


def passive_perception(wis_score: int, pb: int, proficiency: str | None = None) -> int:
    """
    Passive Perception score: 10 + Wisdom modifier [+ pb if proficient] [+ 2*pb if expert].

    Pass monster["skills"].get("perception") as proficiency:
      "proficient"  →  10 + wis_mod + pb
      "expert"      →  10 + wis_mod + 2*pb
      None          →  10 + wis_mod  (perception not listed in skills)

    Examples:
        passive_perception(14, 4, "proficient") == 16   # 10 + 2 + 4
        passive_perception(14, 4, "expert")     == 20   # 10 + 2 + 8
        passive_perception(10, 2)               == 10   # 10 + 0, not listed
    """
    mod = ability_modifier(wis_score)
    if proficiency == "expert":
        return 10 + mod + 2 * pb
    if proficiency == "proficient":
        return 10 + mod + pb
    return 10 + mod


def damage_average(dice_count: int, dice_type: int, modifier: int) -> int:
    """
    Expected average of a damage roll.

    For dice-based rolls: floor(dice_count × (dice_type + 1) / 2) + modifier.
    For flat (no-dice) rolls (dice_count == 0): returns modifier directly.

    Examples:
        damage_average(2, 8, 4)  == 13   # 2d8+4
        damage_average(2, 8, 0)  == 9    # 2d8
        damage_average(0, 0, 1)  == 1    # flat 1 damage
    """
    return math.floor(dice_count * (dice_type + 1) / 2) + modifier


def damage_formula(dice_count: int, dice_type: int, modifier: int) -> str:
    """
    Human-readable damage formula string.

    For flat (no-dice) rolls (dice_count == 0): returns the modifier as a string.

    Examples:
        damage_formula(2, 8, 4)   == "2d8+4"
        damage_formula(2, 8, 0)   == "2d8"
        damage_formula(2, 8, -2)  == "2d8-2"
        damage_formula(0, 0, 1)   == "1"
    """
    if dice_count == 0:
        return str(modifier)
    base = f"{dice_count}d{dice_type}"
    if modifier > 0:
        return f"{base}+{modifier}"
    if modifier < 0:
        return f"{base}{modifier}"
    return base


def saving_throw(score: int, pb: int, proficiency: str | None = None) -> int:
    """
    Saving throw bonus for a given ability score and proficiency level.

    proficiency values (from the save_proficiency field in monsters.json):
      None / absent  →  unproficient: ability modifier only
      "proficient"   →  ability modifier + proficiency bonus
      "expert"       →  ability modifier + 2 × proficiency bonus

    Examples:
        saving_throw(21, 4)                   == 5   # STR 21, no proficiency
        saving_throw(21, 4, "proficient")     == 9   # STR 21, proficient
        saving_throw(21, 4, "expert")         == 13  # STR 21, expertise
    """
    mod = ability_modifier(score)
    if proficiency == "expert":
        return mod + 2 * pb
    if proficiency == "proficient":
        return mod + pb
    return mod
