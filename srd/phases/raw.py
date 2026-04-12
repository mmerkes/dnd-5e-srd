#!/usr/bin/env python3
"""
Phase 1: Extract raw text for each monster stat block from the SRD PDF.

Handles the two-column page layout and identifies monster boundaries by
detecting the distinctive size/type/alignment line that follows every
monster name.

Usage:  python3 -m srd.phases.raw              # full run: PDF extraction + split
        python3 -m srd.phases.raw --split-only  # re-split existing raw_combined.txt
Output: output/raw/<monster_slug>.txt  — one file per monster
        output/raw_combined.txt        — full extracted text for debugging
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

# Project root is three levels up from this file (srd/phases/raw.py).
# All paths are anchored here so the script works regardless of cwd.
_ROOT = Path(__file__).resolve().parent.parent.parent

PDF_PATH  = _ROOT / "SRD_CC_v5.2.1.pdf"
OUTPUT_DIR = _ROOT / "output" / "raw"

# Pages in the PDF (1-indexed, as printed in the book).
# pdfplumber uses 0-indexed internally; we subtract 1 when accessing pages.
# The SRD 5.2.1 monster section starts at 258 and runs to the end of the PDF.
FIRST_PAGE = 258
LAST_PAGE = 364  # end of PDF; includes Appendix beasts (344–364)

# ---------------------------------------------------------------------------
# Monster-boundary detection
# ---------------------------------------------------------------------------

_SIZE_WORD = r"(?:Tiny|Small|Medium|Large|Huge|Gargantuan)"
SIZES = rf"{_SIZE_WORD}(?:\s+or\s+{_SIZE_WORD})?"

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

# The second line of every stat block is size + type (+ optional tag) + alignment.
# When we find this line, the preceding non-empty line is the monster name.
META_RE = re.compile(
    rf"^({SIZES})\s+({CREATURE_TYPES})\s*(\(.*?\))?\s*,\s*({ALIGNMENTS})\s*$",
    re.IGNORECASE | re.MULTILINE,
)


# ---------------------------------------------------------------------------
# PDF text extraction helpers
# ---------------------------------------------------------------------------

def find_column_split(words: list[dict], page_width: float) -> float:
    """
    Identify the x-coordinate that divides the two text columns.

    We scan for the widest horizontal gap in word coverage within the
    central 60 % of the page.  Falls back to page centre if no clear gap.

    Why the central 60%?  Page margins and narrow words near either edge
    create spurious gaps; limiting the search to the centre avoids those
    and finds only the true gutter between columns.
    """
    page_mid = page_width / 2
    margin = page_mid * 0.3  # search ±30% around the midpoint
    search_lo = int(page_mid - margin)
    search_hi = int(page_mid + margin)

    # Mark every pixel-column occupied by at least one word
    occupied: set[int] = set()
    for w in words:
        occupied.update(range(int(w["x0"]), int(w["x1"]) + 1))

    best_mid = page_mid
    best_len = 0
    in_gap = False
    gap_start = 0

    for x in range(search_lo, search_hi):
        if x not in occupied:
            if not in_gap:
                in_gap, gap_start = True, x
        else:
            if in_gap:
                gap_len = x - gap_start
                if gap_len > best_len:
                    best_len = gap_len
                    best_mid = gap_start + gap_len / 2
                in_gap = False

    return best_mid if best_len > 5 else page_mid


def words_to_text(words: list[dict]) -> str:
    """Reconstruct a readable text string from a position-sorted word list."""
    if not words:
        return ""

    # Sort by row first (quantised to 3-pixel bands to merge near-identical tops),
    # then by x within each row.  The quantisation prevents slight vertical jitter
    # from the PDF typesetter from scattering words across multiple logical lines.
    words = sorted(words, key=lambda w: (round(w["top"] / 3) * 3, w["x0"]))

    lines: list[str] = []
    current_words: list[str] = []
    current_top: float = words[0]["top"]
    Y_TOL = 4  # pixels; words within this vertical range are on the same line

    for w in words:
        if abs(w["top"] - current_top) > Y_TOL:
            if current_words:
                lines.append(" ".join(current_words))
            current_words = [w["text"]]
            current_top = w["top"]
        else:
            current_words.append(w["text"])

    if current_words:
        lines.append(" ".join(current_words))

    return "\n".join(lines)


def extract_page_text(page) -> str:
    """
    Extract text from one page in correct reading order.

    Splits the page at the column boundary, extracts each column
    top-to-bottom, then concatenates left column before right column.
    """
    words = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=False)
    if not words:
        return ""

    split_x = find_column_split(words, page.width)

    left_words  = [w for w in words if w["x1"] <= split_x]
    right_words = [w for w in words if w["x0"] >  split_x]

    parts = [col for col in (words_to_text(left_words), words_to_text(right_words)) if col.strip()]
    return "\n".join(parts)


# Page footer pattern (e.g. "319 System Reference Document 5.2.1")
_FOOTER_RE = re.compile(r"^\d+\s+System Reference Document[\d\s.]+$", re.MULTILINE)

# Hyphenated line-break (soft hyphen inserted by the PDF typesetter)
# e.g. "Scorch-\ning Ray"  →  "Scorching Ray"
_HYPHEN_BREAK_RE = re.compile(r"([A-Za-z])-\n([a-z])")


def clean_text(text: str) -> str:
    """Strip page footers and rejoin hyphenated line breaks."""
    text = _FOOTER_RE.sub("", text)
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)
    # Collapse runs of blank lines left by footer removal
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def extract_all_text(pdf_path: Path, first_page: int, last_page: int) -> str:
    """Extract and concatenate text from the given inclusive page range."""
    pages: list[str] = []
    total = last_page - first_page + 1

    with pdfplumber.open(pdf_path) as pdf:
        for i, page_idx in enumerate(range(first_page - 1, last_page)):
            print(f"\r  Page {first_page + i}/{last_page}  ({i + 1}/{total})", end="", flush=True)
            pages.append(extract_page_text(pdf.pages[page_idx]))

    print()  # end progress line
    full = "\n".join(pages)
    return clean_text(full)


# ---------------------------------------------------------------------------
# Monster boundary splitting
# ---------------------------------------------------------------------------

def split_into_monsters(full_text: str) -> list[tuple[str, str]]:
    """
    Return a list of (monster_name, raw_block_text) pairs.

    Algorithm:
      1. Find every line that matches META_RE (the size/type/alignment line).
      2. The last non-empty line before each META_RE match is the monster name.
      3. A block runs from its name line up to (but not including) the name
         line of the next monster.
    """
    lines = full_text.splitlines()

    # Indices of lines that match the meta pattern
    meta_indices: list[int] = [i for i, ln in enumerate(lines) if META_RE.match(ln.strip())]
    print(f"  Found {len(meta_indices)} monster boundaries")

    monsters: list[tuple[str, str]] = []

    for pos, meta_idx in enumerate(meta_indices):
        # Walk back from meta line to find the name
        name_idx = meta_idx - 1
        while name_idx >= 0 and not lines[name_idx].strip():
            name_idx -= 1

        if name_idx < 0:
            continue

        monster_name = lines[name_idx].strip()

        # Block ends just before the next monster's name line
        if pos + 1 < len(meta_indices):
            next_meta = meta_indices[pos + 1]
            next_name_idx = next_meta - 1
            while next_name_idx > meta_idx and not lines[next_name_idx].strip():
                next_name_idx -= 1
            next_name = lines[next_name_idx].strip()
            end_idx = next_name_idx

            # PDF layout artifact: when a two-column page break falls in the
            # middle of an entry, the NEXT monster's name is typeset at the top
            # of the right column of the same page — and also appears at the
            # bottom of the left column as a "column header" to help the reader
            # follow the flow.  pdfplumber sees both copies in reading order,
            # so the next monster's name ends up inside the current block's
            # text.  Trim to the first occurrence of that name inside this block.
            for scan in range(meta_idx + 1, end_idx):
                if lines[scan].strip() == next_name:
                    end_idx = scan
                    break
        else:
            end_idx = len(lines)

        block_text = "\n".join(lines[name_idx:end_idx]).strip()
        monsters.append((monster_name, block_text))

    return monsters


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    """Convert a monster name to a filesystem-safe slug."""
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "_", slug)
    return slug.strip("_-")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    split_only = "--split-only" in sys.argv

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined_path = _ROOT / "output" / "raw_combined.txt"

    if split_only:
        if not combined_path.exists():
            print(f"Error: {combined_path} not found. Run without --split-only first.")
            sys.exit(1)
        print(f"Re-splitting existing {combined_path} …")
        full_text = combined_path.read_text(encoding="utf-8")
    else:
        print(f"Extracting pages {FIRST_PAGE}–{LAST_PAGE} from {PDF_PATH} …")
        full_text = extract_all_text(PDF_PATH, FIRST_PAGE, LAST_PAGE)

        combined_path.parent.mkdir(parents=True, exist_ok=True)
        combined_path.write_text(full_text, encoding="utf-8")
        print(f"  Saved combined text → {combined_path}")

    print("Splitting into individual monster blocks …")
    monsters = split_into_monsters(full_text)
    print(f"  Identified {len(monsters)} monsters")

    for name, block in monsters:
        out_path = OUTPUT_DIR / f"{slugify(name)}.txt"
        out_path.write_text(block, encoding="utf-8")

    print(f"  Wrote {len(monsters)} files → {OUTPUT_DIR}/")
    print(
        "\nPhase 1 complete.\n"
        "  → Review output/raw_combined.txt if the monster count looks wrong.\n"
        "  → Then run:  python3 -m srd.phases.sections"
    )


if __name__ == "__main__":
    main()
