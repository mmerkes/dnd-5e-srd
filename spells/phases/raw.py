#!/usr/bin/env python3
"""
Phase 4: Extract raw text for each spell from the SRD PDF.

Handles the two-column page layout and identifies spell boundaries by
detecting the Level/Cantrip line that immediately follows every spell name.

Uses font-aware character extraction to correctly reconstruct spell names
from the GillSans-SemiBold-SC700 small-caps font, where initial capitals
(size=12) and small-cap letters (size=8.4) are rendered at slightly different
y-positions and must be merged and lowercased to recover the true name.

Usage:  python3 -m spells.phases.raw              # full run: PDF extraction + split
        python3 -m spells.phases.raw --split-only  # re-split existing raw_combined.txt
Output: output/spells/raw/<spell_slug>.txt  — one file per spell
        output/spells/raw_combined.txt      — full extracted text for debugging
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("pdfplumber not installed. Run:  pip3 install pdfplumber")
    sys.exit(1)

# Reuse column-split helper from the monster phase.
from srd.phases.raw import find_column_split, clean_text, slugify

_ROOT = Path(__file__).resolve().parent.parent.parent

PDF_PATH   = _ROOT / "SRD_CC_v5.2.1.pdf"
OUTPUT_DIR = _ROOT / "output" / "spells" / "raw"

# Pages in the PDF (1-indexed, as printed in the book).
# Page 107 begins "Spell Descriptions" and the first spell entry (Acid Arrow).
# Page 175 contains the last spells (Wish, Word of Recall).
# Page 176 starts the Rules Glossary.
FIRST_PAGE = 107
LAST_PAGE  = 175

# Font used for spell names (small-caps variant of GillSans SemiBold).
_SC700_FONT = "SC700"

# Y-tolerance for grouping SC700 characters into a single row.
# Needs to be larger than normal (8 vs 4) because the initial caps (size=12)
# and small-cap letters (size=8.4) sit at slightly different y-positions.
_SC700_Y_TOL = 8

# Y-tolerance for grouping regular body-text characters into rows.
# Char-level tops within one line vary by at most ~2pt (mixed fonts).
# Headers like "Cantrip Upgrade." are 2.4–4pt below the preceding body line;
# using 2 keeps them on separate rows without breaking same-line grouping.
_BODY_Y_TOL = 2

# Threshold (points) for inserting a space between adjacent chars.
_SPACE_GAP = 2


# ---------------------------------------------------------------------------
# Spell-boundary detection
# ---------------------------------------------------------------------------

_SCHOOLS = (
    r"(?:Abjuration|Conjuration|Divination|Enchantment"
    r"|Evocation|Illusion|Necromancy|Transmutation)"
)

# The second line of every spell entry is one of:
#   "Level 2 Evocation (Bard, Wizard)"
#   "Evocation Cantrip (Sorcerer, Wizard)"
SPELL_META_RE = re.compile(
    rf"^(?:Level\s+\d+\s+{_SCHOOLS}|{_SCHOOLS}\s+Cantrip)\s*\(",
    re.IGNORECASE | re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Spell name validator
# ---------------------------------------------------------------------------

# Words that disqualify a candidate line from being a spell name.
# Two-column PDF layout sometimes places a fragment of the previous spell's
# description text immediately before the next spell's name line and meta line.
# Any fragment containing these common spell-text words is not a spell name.
_NAME_REJECTS = re.compile(
    r"\b(damage|save|slot|level|spell|cast|hit|each|increases?|above|below"
    r"|within|target|creature|roll|turn|action)\b",
    re.IGNORECASE,
)


def _is_valid_spell_name(text: str) -> bool:
    """
    Return True if `text` looks like a spell name rather than description text.

    Two-column page layout sometimes places the last line(s) of a previous
    spell's description between the name of the next spell and its level line.
    This filter skips those artifact lines so the correct name is found.
    """
    text = text.strip()
    if not text:
        return False
    if not text[0].isupper():
        return False
    if re.search(r"\d", text):
        return False
    if text[-1] in (".", ",", ";", ":", "!", "?", ")"):
        return False
    if _NAME_REJECTS.search(text):
        return False
    return True


# ---------------------------------------------------------------------------
# Font-aware character extraction
# ---------------------------------------------------------------------------

def _chars_to_text(chars: list[dict]) -> str:
    """Join a sorted (by x0) list of chars into a string, inserting spaces at gaps."""
    if not chars:
        return ""
    result = chars[0]["text"]
    for i in range(1, len(chars)):
        prev, curr = chars[i - 1], chars[i]
        if curr["x0"] - prev["x1"] > _SPACE_GAP:
            result += " "
        result += curr["text"]
    return result


def _extract_column_text(chars: list[dict], col_start: float, col_end: float) -> str:
    """
    Extract readable text from one page column using font-aware char grouping.

    Two-pass algorithm:
      Pass 1 — SC700 spell names:
        Collect GillSans-SemiBold-SC700 chars, group into rows (Y_TOL=8),
        reconstruct clean names by lowercasing small-cap chars (size < 10).
        Record the y-range each name row occupies.

      Pass 2 — body text:
        Collect non-SC700 chars, exclude any whose y-position falls within a
        SC700 name row's y-range (prevents body text from bleeding into name
        lines or getting lost), group into rows (Y_TOL=4), join with spaces.

      Finally interleave both sets of lines by y-position.
    """
    # Restrict to this column with a small tolerance on the right edge.
    col_chars = [
        c for c in chars
        if c.get("x0", 0) >= col_start - 1 and c.get("x1", 0) <= col_end + 5
    ]
    if not col_chars:
        return ""

    # ---- Pass 1: SC700 spell name characters --------------------------------

    sc700 = [c for c in col_chars if _SC700_FONT in (c.get("fontname") or "")]
    sc700.sort(key=lambda c: c["top"])

    name_rows: list[list[dict]] = []
    if sc700:
        cur: list[dict] = [sc700[0]]
        for c in sc700[1:]:
            if abs(c["top"] - cur[0]["top"]) <= _SC700_Y_TOL:
                cur.append(c)
            else:
                name_rows.append(cur)
                cur = [c]
        name_rows.append(cur)

    # Build name lines and record y-ranges to exclude from body text.
    name_lines: list[tuple[float, str]] = []
    sc700_y_ranges: list[tuple[float, float]] = []

    for row in name_rows:
        y_min = min(c["top"] for c in row)
        y_max = max(c["top"] for c in row)
        sc700_y_ranges.append((y_min, y_max))

        row.sort(key=lambda c: c["x0"])
        name = ""
        for c in row:
            ch = c["text"]
            # Small-caps rendering: uppercase letters at size < 10 are
            # actually small versions of lowercase letters — convert them.
            if (c.get("size") or 12) < 10 and ch.isupper():
                ch = ch.lower()
            name += ch

        if name.strip():
            name_lines.append((y_min, name.strip()))

    # ---- Pass 2: body text characters (non-SC700) ---------------------------

    def _in_sc700_range(top: float) -> bool:
        return any(y_min - 2 <= top <= y_max + 4 for y_min, y_max in sc700_y_ranges)

    body = [
        c for c in col_chars
        if _SC700_FONT not in (c.get("fontname") or "")
        and not _in_sc700_range(c["top"])
    ]

    # Sort by exact top then x.  Do NOT quantise the top value here: quantising
    # (e.g. round(top/3)*3) would bucket chars from adjacent lines into the same
    # sort-key, causing them to interleave by x and then thrash the Y_TOL
    # grouper into producing one row per character.
    body.sort(key=lambda c: (c["top"], c["x0"]))

    body_lines: list[tuple[float, str]] = []
    if body:
        cur_row: list[dict] = [body[0]]
        cur_top: float = body[0]["top"]
        for c in body[1:]:
            if abs(c["top"] - cur_top) <= _BODY_Y_TOL:
                cur_row.append(c)
            else:
                text = _chars_to_text(sorted(cur_row, key=lambda x: x["x0"]))
                if text.strip():
                    body_lines.append((cur_top, text))
                cur_row = [c]
                cur_top = c["top"]
        text = _chars_to_text(sorted(cur_row, key=lambda x: x["x0"]))
        if text.strip():
            body_lines.append((cur_top, text))

    # ---- Interleave by y-position -------------------------------------------

    all_lines = name_lines + body_lines
    all_lines.sort(key=lambda x: x[0])
    return "\n".join(text for _, text in all_lines)


def extract_page_text(page) -> str:
    """
    Extract text from one page in correct reading order.

    Uses character-level font-aware extraction (see _extract_column_text) so
    that SC700 spell names are reconstructed cleanly rather than garbled by
    word-level y-tolerance mixing.
    """
    chars = page.chars
    if not chars:
        return ""

    # Use word extraction only for column-split detection (font-agnostic).
    words = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=False)
    split_x = find_column_split(words, page.width) if words else page.width / 2

    left_text  = _extract_column_text(chars, 0,       split_x)
    right_text = _extract_column_text(chars, split_x, page.width)

    parts = [t for t in (left_text, right_text) if t.strip()]
    return "\n".join(parts)


def extract_all_text(pdf_path: Path, first_page: int, last_page: int) -> str:
    """Extract and concatenate text from the given inclusive page range."""
    pages: list[str] = []
    total = last_page - first_page + 1

    with pdfplumber.open(pdf_path) as pdf:
        for i, page_idx in enumerate(range(first_page - 1, last_page)):
            print(f"\r  Page {first_page + i}/{last_page}  ({i + 1}/{total})", end="", flush=True)
            pages.append(extract_page_text(pdf.pages[page_idx]))

    print()
    full = "\n".join(pages)
    return clean_text(full)


# ---------------------------------------------------------------------------
# Spell boundary splitting
# ---------------------------------------------------------------------------

def split_into_spells(full_text: str) -> list[tuple[str, str]]:
    """
    Return a list of (spell_name, raw_block_text) pairs.

    Algorithm:
      1. Find every line that matches SPELL_META_RE (the level/cantrip line).
      2. Walking back from the level line, the first line that passes
         _is_valid_spell_name() is the spell name.  This skips description
         fragments that two-column layout sometimes places between the name
         and its level line.
      3. A block runs from its name line up to (but not including) the name
         line of the next spell.
    """
    lines = full_text.splitlines()

    meta_indices = [i for i, ln in enumerate(lines) if SPELL_META_RE.match(ln.strip())]
    print(f"  Found {len(meta_indices)} spell boundaries")

    spells: list[tuple[str, str]] = []

    for pos, meta_idx in enumerate(meta_indices):
        # Walk back from the level line to find the spell name.
        spell_name = None
        name_idx = meta_idx - 1
        while name_idx >= 0 and (meta_idx - name_idx) <= 8:
            ln = lines[name_idx].strip()
            if ln and _is_valid_spell_name(ln):
                spell_name = ln
                break
            name_idx -= 1

        if spell_name is None:
            continue

        # Block ends just before the next spell's meta line.
        if pos + 1 < len(meta_indices):
            next_meta = meta_indices[pos + 1]

            # Identify the next spell's name using the same _is_valid_spell_name
            # filter used for the current spell.  Without this, body-text lines
            # immediately before the meta line (e.g. "chill shield.") would be
            # mistaken for the spell name and used as the carry-over filter key.
            next_name: str | None = None
            ni = next_meta - 1
            while ni > meta_idx and (next_meta - ni) <= 8:
                ln = lines[ni].strip()
                if ln and _is_valid_spell_name(ln):
                    next_name = ln
                    break
                ni -= 1
            if next_name is None:
                ni = next_meta - 1
                while ni > meta_idx and not lines[ni].strip():
                    ni -= 1
                next_name = lines[ni].strip()

            # Build the block from name_idx up to (not including) the next
            # spell's meta line, then filter out every line that is exactly
            # the next spell's name.  This removes both the actual name line
            # (which sits right before the meta) AND any column carry-over
            # copies of that name that appear earlier in the block, while
            # preserving description text that follows a carry-over (e.g.
            # "chill shield." appearing after a carry-over "Fire Storm").
            raw_lines = lines[name_idx:next_meta]
            block_text = "\n".join(
                ln for ln in raw_lines if ln.strip() != next_name
            ).strip()
        else:
            block_text = "\n".join(lines[name_idx:]).strip()
        spells.append((spell_name, block_text))

    return spells


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    split_only = "--split-only" in sys.argv

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined_path = _ROOT / "output" / "spells" / "raw_combined.txt"
    combined_path.parent.mkdir(parents=True, exist_ok=True)

    if split_only:
        if not combined_path.exists():
            print(f"Error: {combined_path} not found. Run without --split-only first.")
            sys.exit(1)
        print(f"Re-splitting existing {combined_path} …")
        full_text = combined_path.read_text(encoding="utf-8")
    else:
        print(f"Extracting pages {FIRST_PAGE}–{LAST_PAGE} from {PDF_PATH} …")
        full_text = extract_all_text(PDF_PATH, FIRST_PAGE, LAST_PAGE)
        combined_path.write_text(full_text, encoding="utf-8")
        print(f"  Saved combined text → {combined_path}")

    print("Splitting into individual spell blocks …")
    spells = split_into_spells(full_text)
    print(f"  Identified {len(spells)} spells")

    # Clear stale output files before writing new ones.
    for old in OUTPUT_DIR.glob("*.txt"):
        old.unlink()

    for name, block in spells:
        out_path = OUTPUT_DIR / f"{slugify(name)}.txt"
        out_path.write_text(block, encoding="utf-8")

    print(f"  Wrote {len(spells)} files → {OUTPUT_DIR}/")
    print(
        "\nPhase 4 complete.\n"
        "  → Review output/spells/raw_combined.txt if the spell count looks wrong.\n"
        "  → Then run:  python3 -m spells.phases.sections"
    )


if __name__ == "__main__":
    main()
