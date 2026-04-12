#!/usr/bin/env python3
"""
Phase 2: Parse raw monster text into labeled sections.

Handles the SRD 5.2.1 stat block format, which differs from 5.1 in several
key ways:
  • AC line includes Initiative: "AC 17 Initiative +7 (17)"
  • Hit points use "HP" prefix: "HP 150 (20d10 + 40)"
  • Challenge uses "CR": "CR 10 (XP 5,900; PB +4)"
  • Ability score table embeds saves: "Str 30 +10 +10  Dex 10 +0 +7 ..."
  • Resistances/Immunities/Vulnerabilities replace the old split fields
  • "Traits" and "Bonus Actions" are explicit section headers

Usage:  python3 -m srd.phases.sections
Input:  output/raw/<monster_slug>.txt
Output: output/sections/<monster_slug>.json
"""

from __future__ import annotations

import re
import json
from pathlib import Path

# Project root is three levels up from this file (srd/phases/sections.py).
_ROOT = Path(__file__).resolve().parent.parent.parent

INPUT_DIR  = _ROOT / "output" / "raw"
OUTPUT_DIR = _ROOT / "output" / "sections"

# ---------------------------------------------------------------------------
# Shared patterns
# ---------------------------------------------------------------------------

SIZES = r"Tiny|Small|Medium|Large|Huge|Gargantuan"
CREATURE_TYPES = (
    r"aberration|beast|celestial|construct|dragon|elemental|fey|fiend|giant"
    r"|humanoid|monstrosity|ooze|plant|undead|swarm of \w+ \w+"
)
ALIGNMENTS = (
    r"lawful good|neutral good|chaotic good"
    r"|lawful neutral|neutral|chaotic neutral"
    r"|lawful evil|neutral evil|chaotic evil"
    r"|unaligned|any.*?alignment"
)

META_RE = re.compile(
    rf"^({SIZES})\s+({CREATURE_TYPES})\s*(\(.*?\))?\s*,\s*({ALIGNMENTS})\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# ---------------------------------------------------------------------------
# SRD 5.2.1 labeled field patterns
# ---------------------------------------------------------------------------

LABELED_FIELDS: dict[str, re.Pattern] = {
    # "AC 17 Initiative +7 (17)"  — we capture everything after "AC "
    # parse_structured.py later splits this into value + initiative_bonus.
    "ac_line":        re.compile(r"^AC (.+)$",              re.MULTILINE),
    # "HP 150 (20d10 + 40)"
    "hp_line":        re.compile(r"^HP (.+)$",              re.MULTILINE),
    # "Speed 10 ft., Swim 40 ft."
    "speed":          re.compile(r"^Speed (.+)$",           re.MULTILINE),
    # "Skills History +12, Perception +10"
    # Skills may wrap to a second line when many skills are listed (e.g. Spy,
    # Ancient Green Dragon, Sphinx of Lore have 3-4 skills that overflow the
    # column width).  The negative lookahead stops capture before any known
    # next-field keyword so we don't accidentally swallow subsequent fields.
    "skills": re.compile(
        r"^Skills (.+(?:\n(?!Gear|Senses|Languages|Resistances|Immunities"
        r"|Vulnerabilities|CR\b|Traits|Actions|Bonus Actions|Reactions|Legendary).+)*)",
        re.MULTILINE,
    ),
    # "Vulnerabilities Fire"
    "vulnerabilities":re.compile(r"^Vulnerabilities (.+)$", re.MULTILINE),
    # "Resistances Acid, Fire; Bludgeoning (nonmagical)"
    "resistances":    re.compile(r"^Resistances (.+)$",     re.MULTILINE),
    # "Immunities Poison; Exhaustion, Poisoned"
    # Before semicolon = damage immunities; after = condition immunities
    "immunities":     re.compile(r"^Immunities (.+)$",      re.MULTILINE),
    # "Senses Darkvision 120 ft.; Passive Perception 20"
    "senses":         re.compile(r"^Senses (.+)$",          re.MULTILINE),
    # "Languages Deep Speech; telepathy 120 ft."
    "languages":      re.compile(r"^Languages (.+)$",       re.MULTILINE),
    # "CR 10 (XP 5,900, or 7,200 in lair; PB +4)"
    "cr_line":        re.compile(r"^CR (.+)$",              re.MULTILINE),
}

# Section headers that introduce blocks of named entries
SECTION_HEADER_RE = re.compile(
    r"^(Traits|Actions|Bonus Actions|Reactions|Legendary Actions|Lair Actions|Villain Actions)\s*$",
    re.MULTILINE,
)

# Ability score table header in 5.2.1
ABILITY_HEADER_RE = re.compile(r"MOD\s+SAVE\s+MOD\s+SAVE\s+MOD\s+SAVE", re.IGNORECASE)

# Known condition names (used to split the Immunities field)
_CONDITIONS = {
    "blinded", "charmed", "deafened", "exhaustion", "frightened",
    "grappled", "incapacitated", "invisible", "paralyzed", "petrified",
    "poisoned", "prone", "restrained", "stunned", "unconscious",
}


# ---------------------------------------------------------------------------
# Ability score parser (5.2.1 format)
# ---------------------------------------------------------------------------

def parse_ability_scores(text: str) -> dict | None:
    """
    Extract the 6 ability scores, modifiers, and saving throw bonuses from
    the SRD 5.2.1 table format.

    The table header is "MOD SAVE MOD SAVE MOD SAVE".
    Each entry appears as one of:
        "Str 21 +5 +5"  (label before numbers)
        "21 +5 +5 Str"  (numbers before label)

    We don't rely on the label position — we extract triplets (score, mod, save)
    in document order, then assign them to stats in canonical order (STR … CHA).
    This handles the inconsistent label placement that pdfplumber produces.

    Returns a dict keyed by lowercase 3-letter stat name with raw string values.
    The 'modifier' key is included here but is dropped by parse_structured.py
    (it's derivable from 'score' via helpers.ability_modifier()).
    """
    header = ABILITY_HEADER_RE.search(text)
    if not header:
        return None

    # Grab text immediately after the header, stopping before the next
    # clearly non-stat line (Skills, Senses, Immunities, Resistances, CR …)
    after = text[header.end():]
    boundary = re.search(
        r"\n(?:Skills|Senses|Languages|Resistances|Immunities|Vulnerabilities|CR\s)",
        after,
    )
    table_text = after[: boundary.start()].strip() if boundary else after[:300].strip()

    # Normalise Unicode minus (−) to ASCII (-) before parsing
    table_text = table_text.replace("\u2212", "-").replace("\u2013", "-")

    # Find all score/modifier/save triplets: unsigned int, signed modifier, signed-or-unsigned save.
    # The save sign is optional ('?') because the Young White Dragon PDF omits the minus
    # on one saving throw, causing '2' to be extracted instead of '-2'.  That specific
    # case is corrected later via corrections.json in parse_structured.py.
    triplets = re.findall(
        r"(\d+)\s+([+\-]\d+)\s+([+\-]?\d+)",
        table_text,
    )
    if len(triplets) < 6:
        return None

    stats = ["str", "dex", "con", "int", "wis", "cha"]
    return {
        stat: {
            "score":         triplets[i][0],
            "modifier":      triplets[i][1],
            "saving_throw":  triplets[i][2],
        }
        for i, stat in enumerate(stats)
    }


# ---------------------------------------------------------------------------
# Immunities splitter
# ---------------------------------------------------------------------------

def split_immunities(raw: str) -> tuple[str, str]:
    """
    Split the raw Immunities value into (damage_immunities, condition_immunities).

    The SRD 5.2.1 format uses a semicolon as the separator:
        "Poison; Exhaustion, Poisoned"
        "Necrotic, Poison; Charmed, Exhaustion, Grappled, Paralyzed, Petrified,
         Poisoned, Prone, Restrained, Unconscious"
        "Blinded, Charmed, Deafened, Frightened"  ← only conditions, no semicolon

    Heuristic: items after the semicolon are conditions; items before are damage
    types.  If there's no semicolon, classify each item by whether it's a known
    condition name.
    """
    if not raw:
        return "", ""

    if ";" in raw:
        parts = raw.split(";", 1)
        return parts[0].strip(), parts[1].strip()

    # No semicolon — classify item by item
    items = [s.strip() for s in raw.split(",") if s.strip()]
    damage, conditions = [], []
    for item in items:
        if item.lower() in _CONDITIONS:
            conditions.append(item)
        else:
            damage.append(item)
    return ", ".join(damage), ", ".join(conditions)


# ---------------------------------------------------------------------------
# Section splitter
# ---------------------------------------------------------------------------

def split_named_sections(text: str) -> dict[str, str]:
    """
    Split text into named sections keyed by lowercase-underscored header name.
    Everything between the CR line and the first explicit header is 'traits'.

    SRD 5.2.1 uses explicit section headers (Traits, Actions, Bonus Actions,
    Reactions, Legendary Actions).  Not every monster has every section.
    Some monsters have no Traits header and the trait text sits between the
    CR line and the first Actions header — both cases are handled.
    """
    sections: dict[str, str] = {
        "traits":           "",
        "actions":          "",
        "bonus_actions":    "",
        "reactions":        "",
        "legendary_actions":"",
        "lair_actions":     "",
    }

    headers = list(SECTION_HEADER_RE.finditer(text))

    # Find where the stat block ends (after CR line)
    cr_m = LABELED_FIELDS["cr_line"].search(text)
    stat_end = cr_m.end() if cr_m else 0

    if headers:
        # Everything between stat block end and first explicit header
        # (Traits section is often blank for simple monsters)
        first_hdr_start = headers[0].start()
        # If the first header IS "Traits", put everything AFTER it in traits
        if headers[0].group(1).lower() == "traits":
            traits_end = headers[1].start() if len(headers) > 1 else len(text)
            sections["traits"] = text[headers[0].end() : traits_end].strip()
            headers = headers[1:]  # consume the Traits header
        else:
            sections["traits"] = text[stat_end : first_hdr_start].strip()
    else:
        sections["traits"] = text[stat_end:].strip()

    for i, hdr in enumerate(headers):
        key   = hdr.group(1).lower().replace(" ", "_")
        start = hdr.end()
        end   = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        sections[key] = text[start:end].strip()

    return sections


# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

def extract_flavor_text(text: str, meta_match: re.Match) -> str:
    """
    Return any lore/flavor text between the monster name and the meta line.
    The first line of text is the monster name; lines after that (if any)
    are flavor text.
    """
    before_meta = text[: meta_match.start()]
    lines = before_meta.strip().splitlines()
    # Skip the first line (name); collect the rest as flavor text
    flavor = " ".join(ln.strip() for ln in lines[1:] if ln.strip())
    return flavor


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def parse_monster_sections(name: str, raw_text: str) -> dict:
    result: dict = {
        "name":  name,
        "_raw":  raw_text,
    }

    # --- Meta line ---
    meta = META_RE.search(raw_text)
    if meta:
        result["meta_raw"]    = meta.group(0).strip()
        result["size"]        = meta.group(1).strip()
        result["type"]        = meta.group(2).strip()
        result["type_tags"]   = meta.group(3).strip("() ") if meta.group(3) else ""
        result["alignment"]   = meta.group(4).strip()
        result["flavor_text"] = extract_flavor_text(raw_text, meta)
    else:
        result.update({"size": "", "type": "", "type_tags": "", "alignment": "", "flavor_text": ""})

    # --- Labeled fields (most are single-line; skills may wrap to a second line) ---
    for field, pattern in LABELED_FIELDS.items():
        m = pattern.search(raw_text)
        if m:
            # Collapse any continuation newlines to spaces
            result[field] = " ".join(m.group(1).split()) if "\n" in m.group(1) else m.group(1).strip()
        else:
            result[field] = ""

    # Split the Immunities field into damage vs condition
    dmg_imm, cond_imm = split_immunities(result.pop("immunities", ""))
    result["damage_immunities_raw"]    = dmg_imm
    result["condition_immunities_raw"] = cond_imm

    # --- Ability scores (with saves) ---
    result["ability_scores_raw"] = parse_ability_scores(raw_text)

    # --- Named sections ---
    sections = split_named_sections(raw_text)
    result["traits_raw"]            = sections["traits"]
    result["actions_raw"]           = sections["actions"]
    result["bonus_actions_raw"]     = sections["bonus_actions"]
    result["reactions_raw"]         = sections["reactions"]
    result["legendary_actions_raw"] = sections["legendary_actions"]
    result["lair_actions_raw"]      = sections["lair_actions"]

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_files = sorted(INPUT_DIR.glob("*.txt"))
    if not input_files:
        print(f"No .txt files found in {INPUT_DIR}/. Run parse_raw.py first.")
        return

    print(f"Parsing sections for {len(input_files)} monsters …")
    errors: list[str] = []

    for txt_path in input_files:
        raw_text  = txt_path.read_text(encoding="utf-8")
        slug_name = txt_path.stem.replace("_", " ").title()

        try:
            sections = parse_monster_sections(slug_name, raw_text)
        except Exception as exc:
            errors.append(f"{txt_path.name}: {exc}")
            continue

        out_path = OUTPUT_DIR / f"{txt_path.stem}.json"
        out_path.write_text(json.dumps(sections, indent=2, ensure_ascii=False), encoding="utf-8")

    if errors:
        print(f"\n  {len(errors)} error(s):")
        for e in errors:
            print(f"    {e}")

    ok = len(input_files) - len(errors)
    print(f"  Wrote {ok} section files → {OUTPUT_DIR}/")
    print(
        "\nPhase 2 complete.\n"
        "  → Spot-check a few files in output/sections/ to verify sections.\n"
        "  → Then run:  python3 -m srd.phases.structured"
    )


if __name__ == "__main__":
    main()
