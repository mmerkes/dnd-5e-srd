#!/usr/bin/env python3
"""
Phase 6: Deep-parse spell section JSON into fully structured spell JSON.

Converts raw string fields from Phase 5 into typed Python values and writes
a single output/spells.json array.

Usage:  python3 -m spells.phases.structured
Input:  output/spells/sections/<slug>.json
Output: output/spells.json
"""

from __future__ import annotations

import re
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent

INPUT_DIR   = _ROOT / "output" / "spells" / "sections"
OUTPUT_FILE = _ROOT / "output" / "spells.json"

# Optional per-spell corrections that override any computed field.
_CORRECTIONS_FILE = _ROOT / "data" / "spell_corrections.json"
_CORRECTIONS: dict = (
    json.loads(_CORRECTIONS_FILE.read_text(encoding="utf-8"))
    if _CORRECTIONS_FILE.exists() else {}
)


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """
    Clean up multi-line PDF body text:
      • Join soft-hyphenated line breaks:  "hy-\nphen" → "hyphen"
      • Collapse remaining newlines to a single space
      • Normalize runs of whitespace to one space
      • Strip leading/trailing whitespace
    """
    if not text:
        return ""
    # Soft hyphen: dash at end of line joined to next line (no space)
    text = re.sub(r"-\n\s*", "", text)
    # Remaining newlines → space
    text = re.sub(r"\n+", " ", text)
    # Collapse runs of spaces/tabs
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Field parsers
# ---------------------------------------------------------------------------

def parse_components(raw: str) -> dict:
    """
    Parse "V, S, M (some material)" into structured form.

    Returns:
        verbal (bool), somatic (bool), material (bool),
        material_desc (str — content of the parentheses, or "")
    """
    if not raw:
        return {"verbal": False, "somatic": False,
                "material": False, "material_desc": ""}

    verbal   = bool(re.search(r"\bV\b", raw))
    somatic  = bool(re.search(r"\bS\b", raw))
    material = bool(re.search(r"\bM\b", raw))

    mat_desc = ""
    if material:
        m = re.search(r"\bM\s*\((.+)\)\s*$", raw, re.DOTALL)
        if m:
            mat_desc = _normalize(m.group(1))

    return {
        "verbal":        verbal,
        "somatic":       somatic,
        "material":      material,
        "material_desc": mat_desc,
    }


def parse_duration(raw: str) -> dict:
    """
    Parse "Concentration, up to 1 minute" etc.

    Returns:
        concentration (bool), duration (str — the human-readable value)
    """
    if not raw:
        return {"concentration": False, "duration": ""}
    concentration = bool(re.search(r"\bConcentration\b", raw, re.IGNORECASE))
    # Strip the "Concentration, up to " prefix to get the bare time value
    duration = re.sub(r"^Concentration,\s*up to\s+", "", raw, flags=re.IGNORECASE).strip()
    return {"concentration": concentration, "duration": duration}


def parse_casting_time(raw: str) -> str:
    """Return normalized casting time string."""
    return _normalize(raw)


def parse_classes(raw: str) -> list[str]:
    """Split "Bard, Druid, Wizard" into ["Bard", "Druid", "Wizard"]."""
    if not raw:
        return []
    return [c.strip() for c in re.split(r",\s*", raw.strip().strip(")")) if c.strip()]


def _slug(name: str) -> str:
    """Convert a spell name to its file slug."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_spell(sections: dict) -> dict:
    """Convert one spell's section JSON into a structured spell dict."""
    name = sections["name"]

    components = parse_components(sections.get("components_raw", ""))
    dur        = parse_duration(sections.get("duration_raw", ""))

    description = _normalize(sections.get("description_raw", ""))
    higher_level = _normalize(sections.get("higher_level_raw", ""))
    cantrip_upgrade = _normalize(sections.get("cantrip_upgrade_raw", ""))

    spell = {
        "slug":          _slug(name),
        "name":          name,
        "level":         sections.get("level", -1),
        "school":        sections.get("school", ""),
        "classes":       parse_classes(sections.get("classes_raw", "")),
        "ritual":        sections.get("ritual", False),
        "casting_time":  parse_casting_time(sections.get("casting_time_raw", "")),
        "range":         sections.get("range_raw", ""),
        "verbal":        components["verbal"],
        "somatic":       components["somatic"],
        "material":      components["material"],
        "material_desc": components["material_desc"],
        "concentration": dur["concentration"],
        "duration":      dur["duration"],
        "description":   description,
        "higher_level":  higher_level,
        "cantrip_upgrade": cantrip_upgrade,
        "embedded_stat_blocks": sections.get("embedded_stat_blocks_raw", []),
    }

    # Apply any manual corrections for this spell
    slug = spell["slug"]
    if slug in _CORRECTIONS:
        spell.update(_CORRECTIONS[slug])

    return spell


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    input_files = sorted(INPUT_DIR.glob("*.json"))
    if not input_files:
        print(f"No JSON files found in {INPUT_DIR}. Run phase 5 first.")
        return

    print(f"Building structured records for {len(input_files)} spells …")

    spells: list[dict] = []
    errors: list[str] = []

    for path in input_files:
        try:
            sections = json.loads(path.read_text(encoding="utf-8"))
            spells.append(build_spell(sections))
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    if errors:
        print(f"  {len(errors)} error(s):")
        for e in errors:
            print(f"    {e}")

    # Sort by level then name for a predictable order.
    spells.sort(key=lambda s: (s["level"], s["name"]))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(spells, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    ok = len(spells) - len(errors)
    print(f"  Wrote {ok} spells → {OUTPUT_FILE}")
    print(
        "\nPhase 6 complete.\n"
        "  → Spot-check output/spells.json.\n"
        "  → Then run:  python3 spell_viewer.py"
    )


if __name__ == "__main__":
    main()
