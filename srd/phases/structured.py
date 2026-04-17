#!/usr/bin/env python3
"""
Phase 3: Deep-parse section JSON files into fully structured monster JSON.

Converts every raw string field from Phase 2 into typed Python values,
handling the SRD 5.2.1 stat block format throughout.

Key differences from 5.1 handled here:
  • AC line now includes Initiative
  • HP / CR field name changes
  • Ability scores now carry saving throw bonuses in the same table
  • Immunities field unifies damage and condition immunities
  • Attack format: "Melee Attack Roll: +9, reach 5 ft."  (no "to hit")
  • "Bonus Actions" section

Computed fields note:
  Ability score modifiers (floor((score - 10) / 2)) and the flat HP bonus
  (CON modifier × dice_count) are intentionally excluded from the JSON output
  since they are purely derived from other stored values.  Use helpers.py to
  compute them at query time.

Usage:  python3 -m srd.phases.structured
Input:  output/sections/<monster_slug>.json
Output: output/monsters.json
"""

from __future__ import annotations

import re
import json
from pathlib import Path

from srd.helpers import ability_modifier, proficiency_bonus as compute_pb

# Project root is three levels up from this file (srd/phases/structured.py).
_ROOT = Path(__file__).resolve().parent.parent.parent

INPUT_DIR        = _ROOT / "output" / "sections"
OUTPUT_FILE      = _ROOT / "output" / "monsters.json"
VARIANT_FILE     = _ROOT / "data" / "variant_mapping.json"
CORRECTIONS_FILE = _ROOT / "data" / "corrections.json"

_VARIANT_MAP: dict[str, str] = (
    json.loads(VARIANT_FILE.read_text(encoding="utf-8"))
    if VARIANT_FILE.exists() else {}
)

_CORRECTIONS: dict = (
    json.loads(CORRECTIONS_FILE.read_text(encoding="utf-8"))
    if CORRECTIONS_FILE.exists() else {}
)


# ---------------------------------------------------------------------------
# Field parsers — stat block header
# ---------------------------------------------------------------------------

def parse_ac_line(raw: str) -> dict:
    """
    'AC 17 Initiative +7 (17)'  → {"value": 17, "initiative_bonus": 7}
    'AC 9 Initiative −1 (9)'   → {"value": 9,  "initiative_bonus": -1}
    'AC 22'                     → {"value": 22}

    Returns only the raw parsed values; the caller unpacks them into separate
    top-level fields ("armor_class" and "initiative_bonus") on the monster object.
    initiative_score is intentionally omitted — use helpers.initiative_score().
    """
    if not raw:
        return {}
    raw = raw.strip()
    # Normalise Unicode minus (−) and en-dash to ASCII hyphen so the signed-
    # integer patterns below match negative initiative bonuses such as "−1".
    raw = raw.replace("\u2212", "-").replace("\u2013", "-")

    result: dict = {}

    # AC value is always the first number
    ac_m = re.match(r"(\d+)", raw)
    if ac_m:
        result["value"] = int(ac_m.group(1))

    # Initiative: "Initiative +7 (17)" — capture bonus only; score is derived
    init_m = re.search(r"Initiative\s+([+\-]\d+)\s*\(\d+\)", raw, re.IGNORECASE)
    if init_m:
        result["initiative_bonus"] = int(init_m.group(1))

    # Armour type parenthetical (fallback for 5.1-style lines)
    if not init_m:
        type_m = re.search(r"\(([^)]+)\)", raw)
        if type_m:
            result["type"] = type_m.group(1).strip()

    return result


def parse_hit_points(raw: str) -> dict:
    """
    '150 (20d10 + 40)'  (the 'HP ' prefix is stripped by Phase 2)
        → {"dice_count": 20, "dice_type": 10}
    '1 (1d4 − 1)'       (Unicode minus)
        → {"dice_count": 1, "dice_type": 4}

    average and formula are intentionally omitted — use helpers.hp_average() and
    helpers.hp_formula() to compute them at query time (they require the CON score).
    """
    if not raw:
        return {}

    raw = raw.replace("\u2212", "-").replace("\u2013", "-")
    m = re.match(r"(\d+)\s*(?:\((\d+)d(\d+)\s*([+\-]\s*\d+)?\))?", raw)
    if not m:
        return {"raw": raw}

    if m.group(2):
        return {
            "dice_count": int(m.group(2)),
            "dice_type":  int(m.group(3)),
        }

    # Flat HP (no dice expression) — store average as-is
    return {"average": int(m.group(1))}


def parse_speed(raw: str) -> dict:
    """
    '30 ft., Fly 80 ft.'            → {"walk": 30, "fly": 80}
    '20 ft., Burrow 20 ft.'         → {"walk": 20, "burrow": 20}
    '5 ft., Fly 60 ft. (hover)'     → {"walk": 5, "fly": 60, "hover": true}
    '0 ft., Swim 30 ft.'            → {"walk": 0, "swim": 30}
    """
    if not raw:
        return {}

    result: dict = {}

    walk_m = re.match(r"^(\d+)\s*ft\.", raw, re.IGNORECASE)
    if walk_m:
        result["walk"] = int(walk_m.group(1))

    for mode in ("burrow", "climb", "fly", "swim"):
        m = re.search(rf"\b{mode}\s+(\d+)\s*ft\.", raw, re.IGNORECASE)
        if m:
            result[mode] = int(m.group(1))

    if re.search(r"\(hover\)", raw, re.IGNORECASE):
        result["hover"] = True

    return result


def parse_challenge(raw: str) -> dict:
    """
    '10 (XP 5,900, or 7,200 in lair; PB +4)'
        → {"rating": "10", "xp": 5900, "xp_lair": 7200, "proficiency_bonus": 4}
    '1/4 (XP 50; PB +2)'
        → {"rating": "1/4", "xp": 50, "proficiency_bonus": 2}
    '0 (XP 0; PB +2)'
        → {"rating": "0", "xp": 0, "proficiency_bonus": 2}
    """
    if not raw:
        return {}

    raw = raw.replace("\u2212", "-")
    result: dict = {}

    cr_m = re.match(r"([\d/]+)", raw)
    if cr_m:
        result["rating"] = cr_m.group(1)

    # Standard XP: "XP 5,900" or "2,300 XP" (format varies in the PDF)
    xp_m = re.search(r"(?:XP\s+([\d,]+)|([\d,]+)\s*XP)", raw, re.IGNORECASE)
    if xp_m:
        raw_xp = xp_m.group(1) or xp_m.group(2)
        result["xp"] = int(raw_xp.replace(",", ""))

    # Lair XP: "or 7,200 in lair"
    lair_m = re.search(r"or\s+([\d,]+)\s+in\s+lair", raw, re.IGNORECASE)
    if lair_m:
        result["xp_lair"] = int(lair_m.group(1).replace(",", ""))

    # proficiency_bonus intentionally omitted — use helpers.proficiency_bonus(rating).

    return result


# ---------------------------------------------------------------------------
# Ability scores (5.2.1 — saves embedded)
# ---------------------------------------------------------------------------

def parse_ability_scores(raw: dict | None) -> dict:
    """
    Convert raw ability score data from Phase 2 into typed ints.

    Input (from parse_sections.py):
        {"str": {"score": "21", "modifier": "+5", "saving_throw": "+5"}, …}

    Output (intermediate — saving_throw_raw stripped by _resolve_save_proficiencies):
        {"str": {"score": 21, "_saving_throw_raw": 5}, …}

    The ability score modifier and saving throw value are intentionally omitted
    from final JSON — use helpers.ability_modifier() and helpers.saving_throw()
    to compute them at query time.
    """
    if not raw:
        return {}

    result: dict = {}
    for stat, vals in raw.items():
        score = int(vals["score"])
        save  = int(str(vals["saving_throw"]).replace("\u2212", "-"))
        result[stat] = {
            "score":              score,
            "_saving_throw_raw":  save,
        }
    return result


def _resolve_save_proficiencies(
    ability_scores: dict, pb: int | None, name: str = ""
) -> dict:
    """
    Replace the temporary _saving_throw_raw int with a save_proficiency enum.

    Compares the raw save value against ability_modifier(score) and
    ability_modifier(score) + pb to determine proficiency level:
      - equal to mod + 2*pb  →  "expert"   (not expected in SRD, but handled)
      - equal to mod + pb    →  "proficient"
      - anything else        →  key absent (unproficient or unresolvable)

    When pb is None the raw value can't be classified; the key is omitted.

    Design rationale: we store "proficient"/"expert" rather than the numeric
    bonus so that consumers can always recompute the correct value given any
    house-rule PB override, without needing to re-parse the PDF.

    Manual overrides from corrections.json are applied before inference to fix
    PDF rendering artifacts (e.g. the Young White Dragon's INT save renders
    without its minus sign in the PDF).
    """
    overrides = _CORRECTIONS.get("ability_scores", {}).get(name, {})
    result: dict = {}
    for stat, vals in ability_scores.items():
        score    = vals["score"]
        save_raw = vals.pop("_saving_throw_raw")

        # Apply manual correction if present
        stat_overrides = overrides.get(stat, {})
        if "_saving_throw_raw_override" in stat_overrides:
            save_raw = stat_overrides["_saving_throw_raw_override"]

        mod      = ability_modifier(score)
        entry: dict = {"score": score}
        if pb is not None:
            if save_raw == mod + 2 * pb:
                entry["save_proficiency"] = "expert"
            elif save_raw == mod + pb:
                entry["save_proficiency"] = "proficient"
            # else: unproficient — key absent
        result[stat] = entry
    return result


# ---------------------------------------------------------------------------
# Derived stat helpers
# ---------------------------------------------------------------------------

_SKILL_TO_STAT: dict[str, str] = {
    "acrobatics":     "dex",
    "animal_handling":"wis",
    "arcana":         "int",
    "athletics":      "str",
    "deception":      "cha",
    "history":        "int",
    "insight":        "wis",
    "intimidation":   "cha",
    "investigation":  "int",
    "medicine":       "wis",
    "nature":         "int",
    "perception":     "wis",
    "performance":    "cha",
    "persuasion":     "cha",
    "religion":       "int",
    "sleight_of_hand":"dex",
    "stealth":        "dex",
    "survival":       "wis",
}


def _parse_skills_raw(raw: str) -> dict[str, int]:
    """Parse skill text into {skill_name: flat_bonus} — intermediate form."""
    if not raw:
        return {}
    return {
        m.group(1).strip().lower().replace(" ", "_"): int(m.group(2))
        for m in re.finditer(r"([A-Z][a-zA-Z ()/]+?)\s*([+\-]\d+)", raw)
    }


def _resolve_skill_proficiencies(
    skills_raw: dict[str, int],
    ability_scores: dict,
    pb: int | None,
    name: str = "",
) -> dict[str, str]:
    """
    Convert {skill: flat_bonus} → {skill: "proficient" | "expert"}.

    Only skills that appear in a monster's stat block are included — listed
    skills are always at least proficient in 5e, so we never store unproficient
    skills.  Skills whose bonus can't be matched to mod+pb or mod+2*pb are
    silently omitted (SRD anomalies are recorded in corrections.json instead).

    Compares each stored bonus against ability_modifier(stat) + pb and
    ability_modifier(stat) + 2*pb to determine proficiency level.
    Skills that match the raw modifier only (no proficiency) are not present
    in the output — skills are always at least proficient in 5e if listed.

    Manual overrides from corrections.json are applied first.
    """
    overrides = _CORRECTIONS.get("skills", {}).get(name, {})
    result: dict[str, str] = {}

    for skill, bonus in skills_raw.items():
        stat = _SKILL_TO_STAT.get(skill)
        if stat is None or pb is None:
            continue
        score = ability_scores.get(stat, {}).get("score")
        if score is None:
            continue

        # Apply manual override if present
        if skill in overrides:
            result[skill] = overrides[skill]
            continue

        mod = ability_modifier(score)
        if bonus == mod + 2 * pb:
            result[skill] = "expert"
        elif bonus == mod + pb:
            result[skill] = "proficient"
        # else: unresolvable (SRD anomaly) — omit

    return result


def parse_list_field(raw: str) -> list[str]:
    """Comma/semicolon-separated list; '—', '–', '-' means none."""
    if not raw or raw.strip() in ("—", "–", "-"):
        return []
    items: list[str] = []
    for chunk in re.split(r";", raw):
        items.extend(s.strip() for s in chunk.split(",") if s.strip())
    return items


def parse_senses(raw: str) -> dict:
    """
    'Darkvision 120 ft., Tremorsense 30 ft.; Passive Perception 20'
    → {"darkvision": 120, "tremorsense": 30}

    passive_perception is intentionally omitted — use helpers.passive_perception().
    """
    if not raw:
        return {}
    result: dict = {}
    for sense in ("blindsight", "darkvision", "tremorsense", "truesight"):
        m = re.search(rf"\b{sense}\s+(\d+)\s*ft\.", raw, re.IGNORECASE)
        if m:
            result[sense] = int(m.group(1))
    return result


def parse_languages(raw: str) -> list[str]:
    if not raw or raw.strip() in ("—", "–", "-", "None"):
        return []
    # Split on commas, but treat semicolons as additional delimiters
    items: list[str] = []
    for chunk in re.split(r";", raw):
        items.extend(s.strip() for s in chunk.split(",") if s.strip())
    return items


# ---------------------------------------------------------------------------
# Attack and damage parsers (5.2.1 format)
# ---------------------------------------------------------------------------

def parse_attack(description: str) -> dict:
    """
    5.2.1 format:
        "Melee Attack Roll: +9, reach 15 ft."
        "Ranged Attack Roll: +4, range 80/320 ft."
        "Melee or Ranged Attack Roll: +6, reach 5 ft. or range 20/60 ft."

    Also handles spells:
        "Melee Spell Attack Roll: +8, reach 5 ft."
    """
    # Normalise Unicode minus
    description = description.replace("\u2212", "-")

    m = re.search(
        r"(Melee or Ranged|Melee|Ranged)\s+(Weapon\s+|Spell\s+)?Attack Roll:\s*([+\-]\d+)"
        r"(?:,\s*reach\s+(\d+)\s*ft\.)?"
        r"(?:(?:,|\s+or)\s*range\s+(\d+)(?:/(\d+))?\s*ft\.)?",
        description, re.IGNORECASE,
    )
    if not m:
        return {}

    kind = m.group(1).lower().replace(" or ", "_or_")
    subtype = (m.group(2) or "weapon").strip().lower()

    attack: dict = {
        "type":  f"{kind}_{subtype}_attack",
        "bonus": int(m.group(3)),
    }
    if m.group(4):
        attack["reach"] = int(m.group(4))
    if m.group(5):
        attack["range_normal"] = int(m.group(5))
        if m.group(6):
            attack["range_long"] = int(m.group(6))

    return attack


def parse_damage_rolls(description: str) -> list[dict]:
    """
    Extract all damage roll entries from the 'Hit:' clause.

    '13 (2d8 + 4) Bludgeoning damage plus 9 (2d8) Fire damage'
        → [{"dice_count": 2, "dice_type": 8, "modifier": 4, "damage_type": "bludgeoning"},
           {"dice_count": 2, "dice_type": 8, "modifier": 0, "damage_type": "fire"}]

    '4 Piercing damage'  ← flat, no dice
        → [{"dice_count": 0, "dice_type": 0, "modifier": 4, "damage_type": "piercing"}]

    average and formula are intentionally omitted — use helpers.damage_average() and
    helpers.damage_formula() to compute them at query time.
    """
    description = description.replace("\u2212", "-").replace("\u2013", "-")

    hit_m = re.search(r"\bHit:\s*(.+?)(?:\.|$)", description, re.IGNORECASE | re.DOTALL)
    if not hit_m:
        return []

    hit_text = hit_m.group(1)
    rolls: list[dict] = []

    # Dice-based: "13 (2d8 + 4) Bludgeoning damage"
    for m in re.finditer(
        r"(\d+)\s*\((\d+)d(\d+)\s*([+\-]\s*\d+)?\)\s+([\w ]+?)\s+damage",
        hit_text, re.IGNORECASE,
    ):
        modifier = int(m.group(4).replace(" ", "")) if m.group(4) else 0
        rolls.append({
            "dice_count":   int(m.group(2)),
            "dice_type":    int(m.group(3)),
            "modifier":     modifier,
            "damage_type":  m.group(5).strip().lower(),
        })

    # Flat damage: "4 Piercing damage" (only when no dice form found)
    if not rolls:
        for m in re.finditer(r"(\d+)\s+([\w]+)\s+damage", hit_text, re.IGNORECASE):
            flat = int(m.group(1))
            rolls.append({
                "dice_count":   0,
                "dice_type":    0,
                "modifier":     flat,
                "damage_type":  m.group(2).strip().lower(),
            })

    return rolls


# ---------------------------------------------------------------------------
# Spellcasting parser
# ---------------------------------------------------------------------------

# Matches "At Will:", "1/Day:", "2/Day Each:", etc.
_SPELL_FREQ_RE = re.compile(r"\b(At Will|\d+/Day(?:\s+Each)?)\s*:", re.IGNORECASE)


def _split_spell_list(text: str) -> list[str]:
    """Split comma-separated spell names, respecting nested parentheses."""
    spells: list[str] = []
    current: list[str] = []
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
            current.append(c)
        elif c == ")":
            depth -= 1
            current.append(c)
        elif c == "," and depth == 0:
            spell = "".join(current).strip()
            if spell:
                spells.append(spell)
            current = []
            if i + 1 < len(text) and text[i + 1] == " ":
                i += 1
        else:
            current.append(c)
        i += 1
    spell = "".join(current).strip()
    if spell:
        spells.append(spell)
    return spells


def parse_spellcasting(description: str) -> dict | None:
    """
    Parse a Spellcasting action description into structured data.

    Returns None for non-standard blocks (e.g. Hellfire Spellcasting, Spell
    Storing) that don't contain standard frequency markers.

    Input example:
        "The dragon casts one of the following spells, requiring no Material
        components and using Charisma as the spellcasting ability
        (spell save DC 23, +15 to hit with spell attacks):
        At Will: Command (level 2 version), Detect Magic
        1/Day Each: Fireball (level 6 version), Scrying"

    Returns:
        {
            "spellcasting_ability": "charisma",
            "spell_save_dc": 23,
            "spell_attack_bonus": 15,
            "spells": {
                "at_will": ["Command (level 2 version)", "Detect Magic"],
                "per_day": {"1": ["Fireball (level 6 version)", "Scrying"]}
            }
        }
    """
    if not _SPELL_FREQ_RE.search(description):
        return None

    result: dict = {}

    ability_m = re.search(
        r"using\s+(Charisma|Wisdom|Intelligence|Strength|Dexterity|Constitution)"
        r"\s+as the spellcasting ability",
        description, re.IGNORECASE,
    )
    if ability_m:
        result["spellcasting_ability"] = ability_m.group(1).lower()

    dc_m = re.search(r"spell save DC\s+(\d+)", description, re.IGNORECASE)
    if dc_m:
        result["spell_save_dc"] = int(dc_m.group(1))

    atk_m = re.search(r"([+\-]\d+)\s+to hit with spell attacks", description, re.IGNORECASE)
    if atk_m:
        result["spell_attack_bonus"] = int(atk_m.group(1))

    # Trim description down to the spell list portion (from first frequency marker on)
    first_marker = _SPELL_FREQ_RE.search(description)
    spell_list_text = description[first_marker.start():]

    markers = list(_SPELL_FREQ_RE.finditer(spell_list_text))
    spells: dict = {"at_will": [], "per_day": {}}

    for idx, marker in enumerate(markers):
        freq_label = marker.group(1)
        section_start = marker.end()
        section_end = markers[idx + 1].start() if idx + 1 < len(markers) else len(spell_list_text)
        section_text = spell_list_text[section_start:section_end].strip().rstrip(",")

        spell_names = _split_spell_list(section_text)
        if not spell_names:
            continue

        if freq_label.lower() == "at will":
            spells["at_will"] = spell_names
        else:
            count_m = re.match(r"(\d+)", freq_label)
            if count_m:
                spells["per_day"][count_m.group(1)] = spell_names

    result["spells"] = spells
    return result


# ---------------------------------------------------------------------------
# Multiattack parser
# ---------------------------------------------------------------------------

_WORD_TO_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8,
}

# "N ActionName attack(s)" — lazy inner match so multi-word names are captured
# but the engine doesn't over-consume past the first "attacks?" boundary.
_ATTACK_FRAG_RE = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight)\s+([\w '\-\u2019]+?)\s+attacks?\b",
    re.IGNORECASE,
)


def parse_multiattack(description: str) -> list[dict] | None:
    """
    Parse a Multiattack description into a structured attack_pattern list.
    Returns None if no recognisable pattern is found.

    Each entry is one of:
        {"action": "Rend",   "count": 3}
        {"action": "Bite",   "count": 1}
        {"actions": ["Scimitar", "Shortbow"], "count": 2, "any_combination": True}
        {"action": "Fire Breath", "count": 1, "optional": True}         # replaceable
        {"options": ["Paralyzing Breath", "Spellcasting to cast …"],    # A/B choice
         "count": 1, "optional": True}
        {"action": "Paralyzing Tentacles", "use": True}                  # bundled use
        {"actions": ["Fling", "Lightning Strike"], "use": True}          # bundled use (pick)
    """
    if not description:
        return None

    desc = description.strip()
    pattern: list[dict] = []

    # Split into the main sentence and any "It can replace…" sentences that follow.
    sentences = re.split(r"(?<=\.)\s+(?=It\s+can\b)", desc, flags=re.IGNORECASE)
    main_sent = sentences[0]
    replace_sents = sentences[1:]

    # -----------------------------------------------------------------------
    # Main sentence
    # -----------------------------------------------------------------------

    # --- "any combination" pattern ---
    any_combo_m = re.search(
        r"makes\s+(one|two|three|four|five|six|seven|eight)\s+attacks?,\s+"
        r"using\s+(.+?)\s+in\s+any\s+combination",
        main_sent, re.IGNORECASE,
    )
    if any_combo_m:
        count = _WORD_TO_NUM[any_combo_m.group(1).lower()]
        weapons = [w.strip() for w in re.split(r"\s*,\s*(?:or\s+)?|\s+or\s+|\s+and\s+", any_combo_m.group(2)) if w.strip()]
        pattern.append({"actions": weapons, "count": count, "any_combination": True})

    else:
        # Strip the "or it makes …" alternative so we don't double-count required attacks.
        attacks_text = re.sub(
            r",?\s*or\s+it\s+makes\s+.+$", "", main_sent,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Collect all "N ActionName attacks?" fragments.
        for m in _ATTACK_FRAG_RE.finditer(attacks_text):
            count = _WORD_TO_NUM[m.group(1).lower()]
            action = m.group(2).strip().rstrip(",")
            pattern.append({"action": action, "count": count})

        # Collect all "uses? …" clauses — handles both "and uses X" and ", uses X".
        # Each match captures one bundled use action (or group of options).
        for um in re.finditer(
            r"(?:,|\band\b)\s+(?:(?:it|can|also)\s+)*uses?\s+"
            r"((?:either\s+)?[\w '\-\u2019]+(?:,\s*[\w '\-\u2019]+)*(?:\s+or\s+[\w '\-\u2019]+)?)"
            r"(?:\s+twice\b)?(?:\s+if\s+available)?",
            attacks_text, re.IGNORECASE,
        ):
            uses_text = um.group(1).strip().rstrip(".,")
            # Strip trailing "and makes…" (Roper: "Reel, and makes two Bite attacks")
            uses_text = re.sub(r",?\s+and\s+makes?\b.*$", "", uses_text, flags=re.IGNORECASE).strip()
            # Strip trailing "if available"
            uses_text = re.sub(r"\s+if\s+available\b.*$", "", uses_text, flags=re.IGNORECASE).strip()
            uses_text = uses_text.rstrip(".,").strip()

            # "X twice" → count=2
            if re.search(r"\btwice\b", uses_text, re.IGNORECASE):
                action = re.sub(r"\s+twice\b.*$", "", uses_text, flags=re.IGNORECASE).strip()
                pattern.append({"action": action, "use": True, "count": 2})
                continue

            uses_text = re.sub(r"^either\s+", "", uses_text, flags=re.IGNORECASE)
            use_options = [u.strip() for u in re.split(r"\s*,\s*(?:or\s+)?|\s+or\s+", uses_text) if u.strip()]
            if len(use_options) == 1:
                pattern.append({"action": use_options[0], "use": True})
            else:
                pattern.append({"actions": use_options, "use": True})

    # --- "or it makes N X attacks" alternative (Medusa, Barbed Devil, Clay Golem …) ---
    alt_m = re.search(
        r"\bor\s+it\s+makes\s+(one|two|three|four|five|six|seven|eight)\s+([\w '\-\u2019]+?)\s+attacks?\b",
        main_sent, re.IGNORECASE,
    )
    if alt_m:
        count = _WORD_TO_NUM[alt_m.group(1).lower()]
        action = alt_m.group(2).strip()
        pattern.append({"action": action, "count": count, "optional": True, "alternative": True})

    # -----------------------------------------------------------------------
    # Replacement sentences ("It can replace N attack(s) with …")
    # -----------------------------------------------------------------------
    for sent in replace_sents:
        replace_m = re.search(
            r"can\s+replace\s+(?:the\s+)?(\w+)\s+attacks?\s+with\s+"
            r"(?:a\s+(?:use\s+of\s+)?)?(.+?)(?:\s+if\s+available)?\.?\s*$",
            sent, re.IGNORECASE,
        )
        if not replace_m:
            continue

        count_word = replace_m.group(1).lower()
        replacement = replace_m.group(2).strip()
        # Use the count word as a number if possible, else default to 1.
        count = _WORD_TO_NUM.get(count_word, 1)

        # Detect "(A) X or (B) Y" option pairs.
        option_parts = re.split(r"\s+or\s+(?:\([A-Z]\)\s+)?", re.sub(r"^\([A-Z]\)\s+", "", replacement))
        option_parts = [o.strip() for o in option_parts if o.strip()]

        if len(option_parts) > 1:
            pattern.append({"options": option_parts, "count": count, "optional": True})
        else:
            action = re.sub(r"^the\s+", "", replacement, flags=re.IGNORECASE)
            action = re.sub(r"\s+attacks?\s*$", "", action, flags=re.IGNORECASE).strip()
            pattern.append({"action": action, "count": count, "optional": True})

    return pattern if pattern else None


# ---------------------------------------------------------------------------
# Named-block parser (traits, actions, reactions, legendary actions)
# ---------------------------------------------------------------------------


_RECHARGE_RE = re.compile(r"\s*\(Recharge\s+[\d\u2013\u2014\-]+\)", re.IGNORECASE)
# Matches "(2/Day)", "(3/Day Each)", "(3/Day, or 4/Day in Lair)", etc.
_USES_RE     = re.compile(r"\s*\(\d+/Day[^)]*\)",  re.IGNORECASE)
_COSTS_RE    = re.compile(r"\s*\(Costs\s+\d+\s+Actions?\)", re.IGNORECASE)

# Entry-header line: "Name (optional paren). Description starts here"
# The description MUST start on the same line — this prevents bare lines like
# "Bludgeoning damage." from being mistaken for entry starts.
_HEADER_LINE_RE = re.compile(
    r"^([A-Z][A-Za-z '''\-/]+"       # Name: starts uppercase, title-case words
    r"(?:\s*\([^)]*\))?)"             # optional parenthetical
    r"\.\s+"                          # period + space(s)
    r"(.+)"                           # at least one character of description
)

# Names that are NOT real entries (spell references, damage-type continuations,
# wrapped game-term phrases that happen to look like header lines)
_INVALID_NAME_RE = re.compile(
    r"\(level\s+\d|"                              # "(level 3 version)"
    r"\bversion\b|"                               # "… version"
    r"\b(?:acid|bludgeoning|cold|fire|force|"
    r"lightning|necrotic|piercing|poison|"
    r"psychic|radiant|slashing|thunder|damage)"   # damage type at end of name
    r"\s*$"
    r"|\bHit Points?\s*$"                         # wrapped "… 0\nHit Points. Failure:"
    r"|\bSaving Throw\s*$",                       # wrapped "…\nSaving Throw. …"
    re.IGNORECASE,
)

# Description-start patterns that signal a wrapped continuation line, not a new entry.
# e.g. "Ray attacks. It can replace…" — "Ray attacks" looks like a name but the
# description starting with "It can replace" reveals it's a multiattack wrap.
_CONTINUATION_DESC_RE = re.compile(
    r"^(?:it\s+can\s+replace|a\s+use\s+of)\b",
    re.IGNORECASE,
)


def parse_named_blocks(raw_text: str) -> list[dict]:
    """
    Parse a section of text into a list of named entry dicts.

    Uses a line-based approach: a new entry starts whenever a line matches
    "Name. Description…" (description on the same line as name).  This
    naturally prevents bare continuation lines like "Bludgeoning damage."
    from being treated as entry boundaries.

    Each entry contains at minimum: name, description.
    Optional keys added when present:
      recharge      — "5-6" (from "Recharge 5–6" parenthetical)
      uses_per_day  — {"uses": N, ["uses_lair": M], ["each": True]}
      action_cost   — int (legendary action cost, from "Costs N Actions")
      attack        — {type, bonus, reach, range_normal, range_long}
      damage        — [{dice_count, dice_type, modifier, damage_type}, …]
      save          — {dc, stat}

    For Spellcasting entries, additional keys are merged in from
    parse_spellcasting(): spellcasting_ability, spell_save_dc,
    spell_attack_bonus, spells.

    For Multiattack entries, attack_pattern is added from parse_multiattack().
    """
    if not raw_text:
        return []

    # --- Phase 1: split raw text into (name, description_lines) segments ---
    # A new segment starts when a line matches "Name. First words of description".
    # The description must start on the SAME line as the name — this is the key
    # guard against continuation lines like "acid damage." being parsed as names.
    segments: list[tuple[str, list[str]]] = []

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        hm = _HEADER_LINE_RE.match(stripped)
        if (hm
                and not _INVALID_NAME_RE.search(hm.group(1))
                and not _CONTINUATION_DESC_RE.match(hm.group(2))):
            segments.append((hm.group(1).strip(), [hm.group(2).strip()]))
        elif segments:
            # Continuation line — append to the current segment's description
            segments[-1][1].append(stripped)

    # --- Phase 2: build structured entry dicts from each segment ---
    entries: list[dict] = []

    for raw_name, desc_lines in segments:
        desc  = re.sub(r"\s+", " ", " ".join(desc_lines)).strip()
        entry: dict = {"name": raw_name, "description": desc}

        # Recharge (e.g. "Fire Breath (Recharge 5–6)")
        rc = _RECHARGE_RE.search(raw_name)
        if rc:
            rng = re.search(r"[\d]+[\u2013\u2014\-][\d]+|[\d]+", rc.group(0))
            entry["recharge"] = rng.group(0) if rng else rc.group(0).strip("() ")
            entry["name"]     = _RECHARGE_RE.sub("", raw_name).strip()

        # Daily uses (e.g. "Dominate Mind (2/Day)", "Legendary Resistance (3/Day, or 4/Day in Lair)")
        # Stored as a dict so the viewer and consumers can access uses, lair variant, and "each" flag:
        #   {"uses": 3}
        #   {"uses": 3, "uses_lair": 4}
        #   {"uses": 3, "each": True}
        uses = _USES_RE.search(raw_name)
        if uses:
            uses_text   = uses.group(0)
            uses_dict: dict = {}
            cnt = re.search(r"(\d+)/Day", uses_text, re.IGNORECASE)
            if cnt:
                uses_dict["uses"] = int(cnt.group(1))
            lair_m = re.search(r"or\s+(\d+)/Day\s+in\s+Lair", uses_text, re.IGNORECASE)
            if lair_m:
                uses_dict["uses_lair"] = int(lair_m.group(1))
            if re.search(r"\beach\b", uses_text, re.IGNORECASE):
                uses_dict["each"] = True
            entry["uses_per_day"] = uses_dict or None
            entry["name"]         = _USES_RE.sub("", entry["name"]).strip()

        # Legendary action cost (e.g. "Wing Attack (Costs 2 Actions)")
        cost = _COSTS_RE.search(raw_name)
        if cost:
            cnt = re.search(r"Costs\s+(\d+)", raw_name, re.IGNORECASE)
            entry["action_cost"] = int(cnt.group(1)) if cnt else None
            entry["name"]        = _COSTS_RE.sub("", entry["name"]).strip()

        # Attack
        atk = parse_attack(desc)
        if atk:
            entry["attack"] = atk

        # Damage rolls
        dmg = parse_damage_rolls(desc)
        if dmg:
            entry["damage"] = dmg

        # Saving throw (e.g. "DC 14 Constitution saving throw"
        #               or   "Constitution Saving Throw: DC 14")
        save_m = re.search(
            r"(?:DC\s+(\d+)\s+(\w+)\s+saving throw"
            r"|(\w+)\s+Saving Throw:\s*DC\s+(\d+))",
            desc, re.IGNORECASE,
        )
        if save_m:
            if save_m.group(1):
                entry["save"] = {"dc": int(save_m.group(1)), "stat": save_m.group(2).lower()[:3]}
            else:
                entry["save"] = {"dc": int(save_m.group(4)), "stat": save_m.group(3).lower()[:3]}

        # Spellcasting sub-structure
        if "spellcasting" in entry["name"].lower():
            sc = parse_spellcasting(desc)
            if sc:
                entry.update(sc)

        # Multiattack sub-structure
        if entry["name"].lower() == "multiattack":
            ap = parse_multiattack(desc)
            if ap:
                entry["attack_pattern"] = ap

        entries.append(entry)

    return entries


def parse_legendary_actions(raw_text: str) -> dict:
    """
    Legendary actions section format in 5.2.1:
        "Legendary Action Uses: 3 (4 in Lair). Immediately after …"
        then named action entries.

    Returns {"description": "…", "actions": […], "uses": 3, "uses_lair": 4}
    """
    if not raw_text:
        return {"description": "", "actions": []}

    result: dict = {"description": "", "actions": []}

    # Extract uses from "Legendary Action Uses: 3 (4 in Lair)."
    uses_m = re.search(
        r"Legendary Action Uses:\s+(\d+)(?:\s*\((\d+)\s+in\s+Lair\))?",
        raw_text, re.IGNORECASE,
    )
    if uses_m:
        result["uses"]      = int(uses_m.group(1))
        if uses_m.group(2):
            result["uses_lair"] = int(uses_m.group(2))

    # Split intro description from action list
    first_entry_re = re.compile(r"^[A-Z][A-Za-z '''\-/]+(?:\s*\([^)]*\))?\.\ ", re.MULTILINE)
    lines = raw_text.strip().splitlines()
    intro_lines: list[str] = []
    action_start = len(lines)

    for i, line in enumerate(lines):
        if first_entry_re.match(line.strip()):
            action_start = i
            break
        intro_lines.append(line)

    result["description"] = " ".join(intro_lines).strip()
    result["actions"]     = parse_named_blocks("\n".join(lines[action_start:]))

    return result


# ---------------------------------------------------------------------------
# Monster assembler
# ---------------------------------------------------------------------------

def build_monster(sections: dict) -> dict:
    """Assemble one fully-structured monster dict from a Phase 2 sections dict."""
    name      = sections.get("name", "")
    variant_of = _VARIANT_MAP.get(name)

    # Challenge must be parsed first: the proficiency bonus it yields is required
    # by _resolve_save_proficiencies and _resolve_skill_proficiencies.
    challenge = parse_challenge(sections.get("cr_line", ""))
    pb        = compute_pb(challenge.get("rating"))

    ability_scores = _resolve_save_proficiencies(
        parse_ability_scores(sections.get("ability_scores_raw")),
        pb,
        name,
    )

    skills = _resolve_skill_proficiencies(
        _parse_skills_raw(sections.get("skills", "")),
        ability_scores,
        pb,
        name,
    )

    out: dict = {
        "source":                 "SRD 5.2.1",
        "name":                   name,
        "flavor_text":            sections.get("flavor_text", ""),
        "size":                   sections.get("size", ""),
        "type":                   sections.get("type", ""),
        "tags":                   [t.strip() for t in sections.get("type_tags", "").split(",") if t.strip()],
        "alignment":              sections.get("alignment", ""),
        "armor_class":            {"value": (_ac := parse_ac_line(sections.get("ac_line", ""))).get("value")},
        "initiative_bonus":       _ac.get("initiative_bonus"),
        "hit_points":             parse_hit_points(sections.get("hp_line", "")),
        "speed":                  parse_speed(sections.get("speed", "")),
        "ability_scores":         ability_scores,
        "skills":                 skills,
        "damage_vulnerabilities": parse_list_field(sections.get("vulnerabilities", "")),
        "damage_resistances":     parse_list_field(sections.get("resistances", "")),
        "damage_immunities":      parse_list_field(sections.get("damage_immunities_raw", "")),
        "condition_immunities":   parse_list_field(sections.get("condition_immunities_raw", "")),
        "senses":                 parse_senses(sections.get("senses", "")),
        "languages":              parse_languages(sections.get("languages", "")),
        "challenge":              challenge,
        "special_abilities":      parse_named_blocks(sections.get("traits_raw", "")),
        "actions":                parse_named_blocks(sections.get("actions_raw", "")),
        "bonus_actions":          parse_named_blocks(sections.get("bonus_actions_raw", "")),
        "reactions":              parse_named_blocks(sections.get("reactions_raw", "")),
        "legendary_actions":      parse_legendary_actions(sections.get("legendary_actions_raw", "")),
        "lair_actions":           parse_named_blocks(sections.get("lair_actions_raw", "")),
    }
    if variant_of:
        out["variant_of"] = variant_of
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    input_files = sorted(INPUT_DIR.glob("*.json"))
    if not input_files:
        print(f"No .json files found in {INPUT_DIR}/. Run parse_sections.py first.")
        return

    print(f"Structuring {len(input_files)} monsters …")
    monsters: list[dict] = []
    errors:   list[str]  = []

    for json_path in input_files:
        sections = json.loads(json_path.read_text(encoding="utf-8"))
        try:
            monster = build_monster(sections)
            monsters.append(monster)
        except Exception as exc:
            errors.append(f"{json_path.name}: {exc}")

    OUTPUT_FILE.write_text(
        json.dumps(monsters, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if errors:
        print(f"\n  {len(errors)} error(s):")
        for e in errors:
            print(f"    {e}")

    print(f"  Wrote {len(monsters)} monsters → {OUTPUT_FILE}")
    print("\nPhase 3 complete.  Final output: output/monsters.json")


if __name__ == "__main__":
    main()
