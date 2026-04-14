#!/usr/bin/env python3
"""
Phase 5: Parse raw spell text into labeled sections.

Extracts labeled fields (Casting Time, Range, Components, Duration) and splits
the remaining description into:
  • description_raw   — main spell text
  • cantrip_upgrade_raw — text after a "Cantrip Upgrade." inline header
  • higher_level_raw  — text after a "Using a Higher-Level Spell Slot." header
  • embedded_stat_blocks_raw — list of raw creature stat block strings

Also handles PDF layout artifacts where inline BoldItalic section headers are
placed at tight line spacing between two halves of a body-text sentence.

Usage:  python3 -m spells.phases.sections
Input:  output/spells/raw/<spell_slug>.txt
Output: output/spells/sections/<spell_slug>.json
"""

from __future__ import annotations

import re
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent

INPUT_DIR  = _ROOT / "output" / "spells" / "raw"
OUTPUT_DIR = _ROOT / "output" / "spells" / "sections"

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_SCHOOLS = (
    r"(?:Abjuration|Conjuration|Divination|Enchantment"
    r"|Evocation|Illusion|Necromancy|Transmutation)"
)

# Matches the full meta line including the (possibly wrapped) class list.
# Group 1 = level digit (absent for cantrips)
# Group 2 = school (Level N spells)
# Group 3 = school (cantrips)
# Group 4 = raw class list text (may contain newlines if list wraps)
SPELL_META_RE = re.compile(
    rf"^(?:Level\s+(\d+)\s+({_SCHOOLS})|({_SCHOOLS})\s+Cantrip)\s*\(([\s\S]+?)\)",
    re.IGNORECASE | re.MULTILINE,
)

# The labeled stat fields that precede the description.
# IMPORTANT: use [ \t]* (not \s*) so the pattern never crosses a newline.
# With \s*, a label-only line ("Casting Time:\n") would match the next line's
# content, silently assigning the wrong value to the field.
# "Components?" handles both "Component:" and "Components:" — both appear in the SRD.
_LABELED: dict[str, re.Pattern] = {
    "casting_time_raw": re.compile(r"^Casting Time:[ \t]*(.+)$",  re.MULTILINE),
    "range_raw":        re.compile(r"^Range:[ \t]*(.+)$",          re.MULTILINE),
    "components_raw":   re.compile(r"^Components?:[ \t]*(.+)$",    re.MULTILINE),
    "duration_raw":     re.compile(r"^Duration:[ \t]*(.+)$",       re.MULTILINE),
}

# Inline bold-italic section headers that split the description.
# These appear as standalone lines in the raw text due to tight PDF line spacing.
_CANTRIP_UPGRADE_RE = re.compile(
    r"^Cantrip Upgrade\.$",
    re.MULTILINE,
)
_HIGHER_LEVEL_RE = re.compile(
    r"^(?:\s*Using a Higher-Level Spell Slot\.)\s*$",
    re.MULTILINE,
)

# Creature type / alignment meta line (for detecting embedded stat blocks).
# Re-uses the same pattern logic as the monster phase, extended with:
#   • "Smaller" in the "or X" clause (e.g. "Huge or Smaller Construct")
_SIZE_WORD = r"(?:Tiny|Small|Medium|Large|Huge|Gargantuan|Smaller)"
_SIZE      = rf"(?:{_SIZE_WORD}(?:\s+or\s+{_SIZE_WORD})?)"
_TYPE      = (r"aberration|beast|celestial|construct|dragon|elemental|fey|fiend"
              r"|giant|humanoid|monstrosity|ooze|plant|undead|swarm of \w+ \w+")
_ALIGN     = (r"lawful good|neutral good|chaotic good"
              r"|lawful neutral|neutral|chaotic neutral"
              r"|lawful evil|neutral evil|chaotic evil"
              r"|unaligned|any.*?alignment")
CREATURE_META_RE = re.compile(
    rf"^({_SIZE})\s+({_TYPE})\s*(?:\(.*?\))?\s*,\s*({_ALIGN})\s*$",
    re.IGNORECASE | re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_at_inline_header(text: str, header_match: re.Match) -> tuple[str, str]:
    """
    Split *text* at an inline bold-italic section header.

    PDF layout places these headers at tight line spacing that sometimes puts
    them between two halves of a body-text sentence.  The lines immediately
    following the header that begin with a lowercase letter are continuations
    of the main description and are appended to *before*.  The first line that
    begins with an uppercase letter starts the new section.

    Returns (before_text, after_text).
    """
    before = text[: header_match.start()]
    rest   = text[header_match.end() :]

    rest_lines  = rest.split("\n")
    continuation: list[str] = []
    new_section:  list[str] = []
    in_new = False

    for line in rest_lines:
        stripped = line.strip()
        if not stripped:
            if in_new:
                new_section.append(line)
            continue
        if in_new:
            new_section.append(line)
        elif stripped[0].islower() or stripped[0] in "(":
            # Lowercase or parenthetical start → continuation of main description
            continuation.append(line)
        else:
            in_new = True
            new_section.append(line)

    before_full = (before.rstrip() + ("\n" + "\n".join(continuation) if continuation else "")).strip()
    return before_full, "\n".join(new_section).strip()


def _extract_embedded_stat_blocks(description: str) -> tuple[str, list[str]]:
    """
    Find embedded creature stat blocks (e.g. Animated Object in Animate Objects).

    A stat block is identified by a Size+Type+Alignment meta line.  Everything
    from that meta line to the end of the description (or the next non-stat-block
    line) is captured as a raw block.

    Returns (description_without_blocks, list_of_raw_blocks).
    """
    meta_matches = list(CREATURE_META_RE.finditer(description))
    if not meta_matches:
        return description, []

    blocks: list[str] = []
    clean_parts: list[str] = []
    prev_end = 0

    for m in meta_matches:
        # Walk back to find the creature name (last non-empty line before the
        # meta line within the description).
        pre_text = description[prev_end : m.start()]
        pre_lines = pre_text.rstrip().splitlines()
        name_line = ""
        name_start = m.start()
        for i in range(len(pre_lines) - 1, -1, -1):
            if pre_lines[i].strip():
                name_line = pre_lines[i].strip()
                # Remove it from the clean part
                pre_lines = pre_lines[:i]
                break
        clean_parts.append("\n".join(pre_lines))

        # The stat block runs from the name line to the end of the description.
        # (If multiple stat blocks exist, each ends where the next one begins.)
        block_start_text = name_line + "\n" + description[m.start() :]
        blocks.append(block_start_text.strip())
        prev_end = len(description)  # consume rest

    return "\n".join(clean_parts).strip(), blocks


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def parse_spell_sections(name: str, raw_text: str) -> dict:
    """Parse a single spell's raw text into labeled section dict."""
    result: dict = {
        "name": name,
        "_raw": raw_text,
    }

    # --- Meta line ---
    meta = SPELL_META_RE.search(raw_text)
    if meta:
        result["meta_raw"] = meta.group(0).strip()
        if meta.group(1):               # Level N Evocation (...)
            result["level"]  = int(meta.group(1))
            result["school"] = meta.group(2).strip()
        else:                           # Evocation Cantrip (...)
            result["level"]  = 0
            result["school"] = meta.group(3).strip()
        # Normalize the class list: collapse newlines and extra spaces.
        classes_raw = re.sub(r"\s+", " ", meta.group(4)).strip().strip(")")
        result["classes_raw"] = classes_raw
    else:
        result.update({"meta_raw": "", "level": -1, "school": "", "classes_raw": ""})

    # --- Labeled stat fields ---
    # Recognises a label-only line ("Range:", "Casting Time:", etc.)
    _FIELD_LABEL_ONLY_RE = re.compile(
        r"^(Casting Time|Range|Components?|Duration):[ \t]*$",
        re.MULTILINE,
    )
    # Recognises any label line (with or without inline value).
    _ANY_LABEL_RE = re.compile(
        r"^(Casting Time|Range|Components?|Duration):[ \t]*",
        re.MULTILINE,
    )

    # Try primary patterns first (inline "Label: Value" format).
    inline_matches: dict[str, re.Match] = {}
    for field, pattern in _LABELED.items():
        m = pattern.search(raw_text)
        if m and m.group(1).strip():
            inline_matches[field] = m

    if len(inline_matches) == len(_LABELED):
        # Happy path: all four fields found on the same line as their label.
        for field, m in inline_matches.items():
            result[field] = m.group(1).strip()
        desc_start = inline_matches["duration_raw"].end()

        # Some casting times wrap to the next line(s) in the PDF
        # (e.g. "Reaction, which you take when you see a\ncreature within 60 feet...").
        # Join any non-label, non-empty continuation lines between CT and Range.
        ct_end   = inline_matches["casting_time_raw"].end()
        rng_start = inline_matches["range_raw"].start()
        if ct_end < rng_start:
            between = raw_text[ct_end:rng_start]
            cont = " ".join(ln.strip() for ln in between.splitlines() if ln.strip())
            if cont:
                result["casting_time_raw"] = (result["casting_time_raw"].rstrip()
                                               + " " + cont)
    else:
        # Fallback for layouts where label lines carry no inline value
        # (e.g. Chill Touch page 115 uses Cambria-Bold separate-line labels).
        # Values appear in the same order as labels but may be separated by
        # other label lines (queue pattern: L1, L2, V1, L3, V2, L4, V3, V4).
        _LABEL_NAME_TO_FIELD = {
            "Casting Time": "casting_time_raw",
            "Range":        "range_raw",
            "Components":   "components_raw",
            "Component":    "components_raw",   # singular variant
            "Duration":     "duration_raw",
        }
        ct_m = re.search(r"^Casting Time:", raw_text, re.MULTILINE)
        if ct_m:
            pending: list[str] = []   # field names waiting for a value
            collected: dict[str, str] = {}
            pos = 0
            desc_start = ct_m.start()
            for raw_ln in raw_text[ct_m.start():].splitlines(keepends=True):
                stripped = raw_ln.strip()
                lm = _ANY_LABEL_RE.match(stripped)
                if lm:
                    label_name = lm.group(1)
                    field = _LABEL_NAME_TO_FIELD.get(label_name)
                    # Check whether the label has an inline value.
                    inline_val = stripped[lm.end():].strip()
                    if inline_val:
                        collected[field] = inline_val
                    else:
                        pending.append(field)
                    pos += len(raw_ln)
                elif stripped and pending:
                    # First non-label, non-empty line satisfies the oldest label.
                    collected[pending.pop(0)] = stripped
                    pos += len(raw_ln)
                    if not pending and len(collected) == 4:
                        desc_start = ct_m.start() + pos
                        break
                elif not stripped:
                    pos += len(raw_ln)
                else:
                    # Non-label, non-empty line with no pending labels → description.
                    desc_start = ct_m.start() + pos
                    break
            for field in _LABELED:
                result[field] = collected.get(field, "")
        else:
            for field in _LABELED:
                result[field] = ""
            desc_start = meta.end() if meta else 0

    # Ritual flag
    result["ritual"] = bool(re.search(r"\bRitual\b", result["casting_time_raw"], re.IGNORECASE))

    # --- Description: everything after the labeled stat fields ---
    desc_raw = raw_text[desc_start:].strip()

    # Some spells (e.g. Wish) start their description with the spell name
    # italicised on its own line (PDF rendering of "*Wish* is the mightiest…").
    # Join that line to the one that follows rather than discarding it.
    desc_lines = desc_raw.splitlines()
    if desc_lines and desc_lines[0].strip() == name:
        rest = desc_lines[1:]
        # The next non-empty line may start with a lowercase continuation
        joined: list[str] = []
        found_first = False
        for ln in rest:
            if not found_first and not ln.strip():
                continue  # skip blank lines between name and continuation
            if not found_first:
                joined.append(name + ln)
                found_first = True
            else:
                joined.append(ln)
        desc_raw = "\n".join(joined).strip()

    # --- Split off "Using a Higher-Level Spell Slot." section ---
    higher_raw = ""
    hl_m = _HIGHER_LEVEL_RE.search(desc_raw)
    if hl_m:
        desc_raw, higher_raw = _split_at_inline_header(desc_raw, hl_m)

    # --- Split off "Cantrip Upgrade." section ---
    cantrip_upgrade_raw = ""
    cu_m = _CANTRIP_UPGRADE_RE.search(desc_raw)
    if cu_m:
        desc_raw, cantrip_upgrade_raw = _split_at_inline_header(desc_raw, cu_m)

    # --- Extract embedded stat blocks from both description and higher_level ---
    desc_raw, blocks_from_desc     = _extract_embedded_stat_blocks(desc_raw)
    higher_raw, blocks_from_higher = _extract_embedded_stat_blocks(higher_raw)
    embedded_blocks = blocks_from_desc + blocks_from_higher

    result["description_raw"]         = desc_raw.strip()
    result["cantrip_upgrade_raw"]      = cantrip_upgrade_raw
    result["higher_level_raw"]         = higher_raw.strip()
    result["embedded_stat_blocks_raw"] = embedded_blocks

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_files = sorted(INPUT_DIR.glob("*.txt"))
    if not input_files:
        print(f"No .txt files found in {INPUT_DIR}. Run phase 4 first.")
        return

    print(f"Parsing sections for {len(input_files)} spells …")
    errors: list[str] = []

    for txt_path in input_files:
        raw_text = txt_path.read_text(encoding="utf-8")
        # Reconstruct the name from the first valid-looking line in the file
        # rather than from the slug (preserves capitalisation and "/" chars).
        first_line = next(
            (ln.strip() for ln in raw_text.splitlines() if ln.strip()),
            txt_path.stem.replace("_", " ").title(),
        )
        name = first_line

        try:
            sections = parse_spell_sections(name, raw_text)
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
        "\nPhase 5 complete.\n"
        "  → Spot-check a few files in output/spells/sections/.\n"
        "  → Then run:  python3 -m spells.phases.structured"
    )


if __name__ == "__main__":
    main()
