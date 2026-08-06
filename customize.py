#!/usr/bin/env python3
"""Interactive, generic Hyprland/Arch Linux customization tool.

A curses TUI that walks three tiers of customizations in order:

  1. Recommended        -- bug fixes and changes almost anyone would want
  2. Opinionated        -- changes the author likes, others might not
  3. Highly opinionated -- changes specific to the author's own setup

Every customization gets its own screen -- including ones that are already
applied or don't apply to this system -- so it's always clear what the tool
is doing. Navigate with the arrow keys (or h/j/k/l, n/p); apply the current
customization with 'a'; quit at any time with 'q'. A report of what was done
is printed when you quit, and is also its own screen you can page back to.

Each customization is a self-contained module under customizations/<tier>/
exposing a module-level CUSTOMIZATION instance. See README.md for how to add
a new one.
"""

from __future__ import annotations

import curses
import importlib
import locale
import pkgutil
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from customizations.base import Detection, Status  # noqa: E402

BANNER = "linux-configurations"

# --------------------------------------------------------------------------
# Big block-letter title font -- a compact 5-row bitmap font, used to render
# page titles large and multi-line instead of as cramped, letter-spaced
# single lines. Only covers what titles actually use: uppercase letters
# (titles are always .upper()'d before lookup), digits, and the punctuation
# that appears in customization titles.
# --------------------------------------------------------------------------

FONT_HEIGHT = 5
BLOCK_CHAR = "█"  # full block

BIG_FONT = {
    "A": (".###.", "#...#", "#####", "#...#", "#...#"),
    "B": ("####.", "#...#", "####.", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "###..", "#....", "#####"),
    "F": ("#####", "#....", "###..", "#....", "#...."),
    "G": (".####", "#....", "#.###", "#...#", ".####"),
    "H": ("#...#", "#...#", "#####", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#..#.", "#.#..", "##...", "#.#..", "#..#."),
    "L": ("#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "####.", "#....", "#...."),
    "Q": (".###.", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "####.", "#..#.", "#...#"),
    "S": (".####", "#....", ".###.", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", ".#.#.", "..#..", ".#.#.", "#...#"),
    "Y": ("#...#", ".#.#.", "..#..", "..#..", "..#.."),
    "Z": ("#####", "...#.", "..#..", ".#...", "#####"),
    "0": (".###.", "#...#", "#.#.#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "#####"),
    "2": (".###.", "#...#", "...#.", "..#..", "#####"),
    "3": ("####.", "....#", "..##.", "....#", "####."),
    "4": ("#..#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "####."),
    "6": (".###.", "#....", "####.", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", "..#.."),
    "8": (".###.", "#...#", ".###.", "#...#", ".###."),
    "9": (".###.", "#...#", ".####", "....#", ".###."),
    " ": ("...", "...", "...", "...", "..."),
    "'": ("#.", "#.", "..", "..", ".."),
    "`": (".#", "#.", "..", "..", ".."),
    "(": (".##", ".#.", "#..", ".#.", ".##"),
    ")": ("##.", ".#.", "..#", ".#.", "##."),
    "!": ("#.", "#.", "#.", "..", "#."),
    "/": ("....#", "...#.", "..#..", ".#...", "#...."),
    "$": (".###.", "#.#..", ".###.", "..#.#", ".###."),
    "-": ("...", "...", "###", "...", "..."),
    ".": ("..", "..", "..", "..", "#."),
}

TIERS = [
    (
        "recommended",
        "Recommended",
        "These are bug fixes and changes almost anyone on this setup would want.",
    ),
    (
        "opinionated",
        "Opinionated",
        "These are changes the author likes, but some people might not.",
    ),
    (
        "highly_opinionated",
        "Highly opinionated",
        "These are changes specific to how the author personally likes their system set up.",
    ),
]


def load_tier(pkg_name):
    items = []
    pkg = importlib.import_module(f"customizations.{pkg_name}")
    for _, mod_name, _ in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m[1]):
        mod = importlib.import_module(f"customizations.{pkg_name}.{mod_name}")
        customization = getattr(mod, "CUSTOMIZATION", None)
        if customization is not None:
            items.append(customization)
    return items


# --------------------------------------------------------------------------
# Page model
# --------------------------------------------------------------------------


@dataclass
class Outcome:
    """Mutable, per-customization state tracked across the session."""

    detection: Detection
    explanation: str = ""
    applied: bool = False
    result: str = ""
    error: str | None = None


@dataclass
class TierPage:
    tier_label: str
    blurb: str
    count: int


@dataclass
class CustomPage:
    tier_label: str
    customization: object
    outcome: Outcome
    position: int  # 1-based index within its tier
    total: int  # customizations in its tier


@dataclass
class ReportPage:
    pass


def build_pages() -> list:
    """Run detection for every customization and lay out the page sequence."""
    pages: list = []
    for pkg_name, tier_label, blurb in TIERS:
        items = load_tier(pkg_name)
        detected = [(c, c.detect()) for c in items]
        pages.append(TierPage(tier_label, blurb, len(detected)))
        for position, (customization, detection) in enumerate(detected, start=1):
            explanation = (
                customization.explain(detection)
                if detection.status == Status.APPLICABLE
                else ""
            )
            outcome = Outcome(detection=detection, explanation=explanation)
            pages.append(CustomPage(tier_label, customization, outcome, position, len(detected)))
    pages.append(ReportPage())
    return pages


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------


def setup_colors() -> dict:
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK
    curses.init_pair(1, curses.COLOR_CYAN, bg)
    curses.init_pair(2, curses.COLOR_GREEN, bg)
    curses.init_pair(3, curses.COLOR_YELLOW, bg)
    curses.init_pair(4, curses.COLOR_RED, bg)
    return {
        "title": curses.color_pair(1) | curses.A_BOLD,
        "applied": curses.color_pair(2) | curses.A_BOLD,
        "pending": curses.color_pair(3) | curses.A_BOLD,
        "dim": curses.A_DIM,
        "error": curses.color_pair(4) | curses.A_BOLD,
        "bar": curses.A_REVERSE,
    }


def safe_addnstr(stdscr, y: int, x: int, text: str, n: int, attr: int = 0) -> None:
    try:
        stdscr.addnstr(y, x, text, n, attr)
    except curses.error:
        pass  # writing to the bottom-right cell raises even though it worked


def wrap_text(text: str, width: int) -> list[str]:
    """Wrap explanatory text for display, preserving blank lines and the
    indentation of already-indented lines (e.g. embedded code snippets)
    instead of re-flowing them as prose.
    """
    width = max(width, 20)
    out: list[str] = []
    for raw in text.split("\n"):
        if raw.strip() == "":
            out.append("")
            continue
        leading = len(raw) - len(raw.lstrip(" "))
        indent = " " * leading
        wrapped = textwrap.wrap(
            raw.strip(), width=max(width - leading, 10),
            initial_indent=indent, subsequent_indent=indent,
        )
        out.extend(wrapped or [""])
    return out


def _glyph(ch: str) -> tuple[str, ...]:
    return BIG_FONT.get(ch, BIG_FONT[" "])


def _big_word_width(word: str) -> int:
    if not word:
        return 0
    total = sum(len(_glyph(ch)[0]) for ch in word)
    return total + (len(word) - 1)  # 1-column gap between letters


def _pack_big_lines(title: str, max_width: int) -> list[list[str]] | None:
    """Word-wrap title into lines of big-font words, each line no wider than
    max_width columns. Returns None if any single word is too wide for its
    own line -- in that case block-letter rendering can't be made to look
    right (mid-word splits are illegible), so the caller should fall back
    to a smaller, non-block rendering instead.
    """
    words = title.upper().split()
    if any(_big_word_width(word) > max_width for word in words):
        return None

    word_gap = 3
    lines: list[list[str]] = []
    current: list[str] = []
    current_width = 0
    for word in words:
        ww = _big_word_width(word)
        added = ww if not current else current_width + word_gap + ww
        if current and added > max_width:
            lines.append(current)
            current, current_width = [word], ww
        else:
            current.append(word)
            current_width = added
    if current:
        lines.append(current)
    return lines


def _render_big_line(chunks: list[str]) -> list[str]:
    rows = [""] * FONT_HEIGHT
    for i, chunk in enumerate(chunks):
        for j, ch in enumerate(chunk):
            glyph = _glyph(ch)
            for r in range(FONT_HEIGHT):
                rows[r] += glyph[r]
            if j != len(chunk) - 1:
                for r in range(FONT_HEIGHT):
                    rows[r] += " "
        if i != len(chunks) - 1:
            for r in range(FONT_HEIGHT):
                rows[r] += "   "
    return [row.replace("#", BLOCK_CHAR).replace(".", " ") for row in rows]


def _resolve_title(title: str, w: int, max_height: int) -> tuple[bool, list, int]:
    """Decide how a title will render given the current width and a row
    budget: as block letters (returns the packed big-font lines) if they
    fit within max_height, otherwise as plain wrapped caps (returns plain
    strings). Also returns the number of terminal rows it will take, so
    callers can measure a title's height before drawing it (e.g. to center
    it) without duplicating this decision.
    """
    max_width = max(w - 4, 4)
    big_lines = _pack_big_lines(title, max_width) if max_width >= FONT_HEIGHT else None
    rows_needed = len(big_lines) * (FONT_HEIGHT + 1) - 1 if big_lines else 0
    if big_lines and rows_needed <= max_height:
        return True, big_lines, rows_needed

    # Fallback: plain wrapped caps, always shown in full -- on a terminal
    # too small to comfortably fit everything, it's the content *below*
    # the title that should give up space, not the title itself.
    small_lines = wrap_text(title.upper(), max(w - 4, 10))
    return False, small_lines, len(small_lines)


def draw_big_title(stdscr, y: int, w: int, title: str, attr: int, max_height: int = 1000) -> int:
    """Render the title as large block letters, word-wrapped across as many
    lines as it takes to stay legible, sized against the *current* terminal
    dimensions every time this is called (so it adapts live to resizes).
    Falls back to smaller, plain wrapped caps when the block-letter version
    doesn't fit in the given width/height. Returns the number of terminal
    rows used, so callers can lay out what follows underneath.
    """
    is_block, lines, rows = _resolve_title(title, w, max_height)
    if is_block:
        cur_y = y
        for chunk in lines:
            rendered = _render_big_line(chunk)
            x = max((w - len(rendered[0])) // 2, 0)
            for r, row_text in enumerate(rendered):
                safe_addnstr(stdscr, cur_y + r, x, row_text, w - x, attr)
            cur_y += FONT_HEIGHT + 1
    else:
        for i, line in enumerate(lines):
            x = max((w - len(line)) // 2, 0)
            safe_addnstr(stdscr, y + i, x, line, w - x, attr)
    return rows


def draw_bar(stdscr, y: int, w: int, text: str, attr: int) -> None:
    safe_addnstr(stdscr, y, 0, text.ljust(w), w, attr)


def status_text_and_attr(outcome: Outcome, colors: dict) -> tuple[str, int]:
    detection = outcome.detection
    if outcome.error:
        return f"ERROR: {outcome.error}", colors["error"]
    if outcome.applied:
        return f"APPLIED -- {outcome.result}", colors["applied"]
    if detection.status == Status.ALREADY_APPLIED:
        reason = f" ({detection.reason})" if detection.reason else ""
        return f"ALREADY APPLIED{reason}", colors["applied"]
    if detection.status == Status.NOT_APPLICABLE:
        reason = detection.reason or "not applicable to this system"
        return f"NOT APPLICABLE -- {reason}", colors["dim"]
    return "NOT YET APPLIED", colors["pending"]


# --------------------------------------------------------------------------
# Page renderers -- each returns the max scroll offset for its body text
# --------------------------------------------------------------------------


def render_tier_page(stdscr, page: TierPage, idx: int, total_pages: int, colors: dict) -> int:
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    draw_bar(stdscr, 0, w, f" {BANNER}   --   page {idx + 1}/{total_pages}", colors["bar"])

    title_text = f"{page.tier_label} customizations"
    blurb_lines = wrap_text(page.blurb, w - 8)
    count_line = (
        f"{page.count} customization{'s' if page.count != 1 else ''} in this tier"
        if page.count
        else "No customizations in this tier yet"
    )

    # Vertically center the whole title+blurb+count block between the bars.
    usable_top, usable_bottom = 1, h - 2
    usable_height = max(usable_bottom - usable_top + 1, 1)
    reserved_below_title = 1 + len(blurb_lines) + 1 + 1  # gap + blurb + gap + count line
    max_title_height = max(usable_height - reserved_below_title, 1)
    _, _, title_rows = _resolve_title(title_text, w, max_title_height)
    content_height = title_rows + reserved_below_title
    title_top = usable_top + max((usable_height - content_height) // 2, 0)

    rows_used = draw_big_title(stdscr, title_top, w, title_text, colors["title"], max_title_height)
    body_top = title_top + rows_used + 1
    for i, line in enumerate(blurb_lines):
        safe_addnstr(stdscr, body_top + i, 4, line, w - 8)
    safe_addnstr(stdscr, body_top + len(blurb_lines) + 1, 4, count_line, w - 8, colors["dim"])
    draw_bar(stdscr, h - 1, w, " n/->: continue    p/<-: back    q: quit", colors["bar"])
    return 0


def render_custom_page(stdscr, page: CustomPage, idx: int, total_pages: int, colors: dict, offset: int) -> int:
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    breadcrumb = f" {page.tier_label}  --  {page.position}/{page.total}    (page {idx + 1}/{total_pages})"
    draw_bar(stdscr, 0, w, breadcrumb, colors["bar"])

    title_top = 2
    status_line, status_attr = status_text_and_attr(page.outcome, colors)
    status_lines = wrap_text(status_line, w - 8)
    # rows reserved below the title: gap + status lines + gap + a few body
    # lines (the body itself scrolls, so it can shrink further) + bottom bar
    min_body = 3
    reserved = 1 + len(status_lines) + 1 + min_body + 1
    max_title_height = max(h - title_top - reserved, 1)
    rows_used = draw_big_title(stdscr, title_top, w, page.customization.title, colors["title"], max_title_height)
    status_top = title_top + rows_used + 1

    for i, line in enumerate(status_lines):
        x = max((w - len(line)) // 2, 0)
        safe_addnstr(stdscr, status_top + i, x, line, w - x, status_attr)

    body_top = status_top + len(status_lines) + 1
    body_bottom = h - 2
    body_height = max(body_bottom - body_top, 0)

    lines = wrap_text(page.outcome.explanation, w - 8) if page.outcome.explanation else []
    max_offset = max(len(lines) - body_height, 0)
    offset = max(0, min(offset, max_offset))
    for i, line in enumerate(lines[offset: offset + body_height]):
        safe_addnstr(stdscr, body_top + i, 4, line, w - 8)

    can_apply = (
        page.outcome.detection.status == Status.APPLICABLE
        and not page.outcome.applied
    )
    hints = ["n/->: next", "p/<-: back"]
    if len(lines) > body_height:
        hints.append("j/k: scroll")
    if can_apply:
        hints.append("a: apply this customization")
    hints.append("q: quit")
    draw_bar(stdscr, h - 1, w, " " + "    ".join(hints), colors["bar"])
    return max_offset


def categorize(pages: list) -> dict[str, list[tuple[CustomPage, Outcome]]]:
    groups: dict[str, list] = {"applied": [], "already": [], "not_applicable": [], "pending": [], "errors": []}
    for page in pages:
        if not isinstance(page, CustomPage):
            continue
        outcome = page.outcome
        if outcome.error:
            groups["errors"].append(page)
        elif outcome.applied:
            groups["applied"].append(page)
        elif outcome.detection.status == Status.ALREADY_APPLIED:
            groups["already"].append(page)
        elif outcome.detection.status == Status.NOT_APPLICABLE:
            groups["not_applicable"].append(page)
        else:
            groups["pending"].append(page)
    return groups


def format_report_lines(pages: list) -> list[str]:
    groups = categorize(pages)
    lines: list[str] = []

    def section(title: str, key: str, describe) -> None:
        items = groups[key]
        lines.append(f"{title} ({len(items)})")
        if not items:
            lines.append("  (none)")
        for page in items:
            lines.append(f"  - {page.customization.title}{describe(page)}")
        lines.append("")

    section("Applied this run", "applied", lambda p: f" -- {p.outcome.result}")
    section("Errors", "errors", lambda p: f" -- {p.outcome.error}")
    section("Already applied", "already", lambda p: f" ({p.outcome.detection.reason})" if p.outcome.detection.reason else "")
    section("Not yet applied", "pending", lambda p: "")
    section("Not applicable", "not_applicable", lambda p: f" ({p.outcome.detection.reason})" if p.outcome.detection.reason else "")

    return lines


def render_report_page(stdscr, pages: list, idx: int, total_pages: int, colors: dict, offset: int) -> int:
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    draw_bar(stdscr, 0, w, f" {BANNER}   --   page {idx + 1}/{total_pages}", colors["bar"])
    title_top = 1
    min_body = 3
    max_title_height = max(h - title_top - (1 + min_body + 1), 1)
    rows_used = draw_big_title(stdscr, title_top, w, "Report", colors["title"], max_title_height)

    body_top = title_top + rows_used + 1
    body_bottom = h - 2
    body_height = max(body_bottom - body_top, 0)

    lines = format_report_lines(pages)
    max_offset = max(len(lines) - body_height, 0)
    offset = max(0, min(offset, max_offset))
    for i, line in enumerate(lines[offset: offset + body_height]):
        safe_addnstr(stdscr, body_top + i, 4, line, w - 8)

    hints = ["p/<-: back"]
    if len(lines) > body_height:
        hints.append("j/k: scroll")
    hints.append("q: quit")
    draw_bar(stdscr, h - 1, w, " " + "    ".join(hints), colors["bar"])
    return max_offset


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------

NEXT_KEYS = {curses.KEY_RIGHT, ord("l"), ord("n")}
PREV_KEYS = {curses.KEY_LEFT, ord("h"), ord("p")}
DOWN_KEYS = {curses.KEY_DOWN, ord("j")}
UP_KEYS = {curses.KEY_UP, ord("k")}
APPLY_KEYS = {ord("a"), ord("A"), 10, 13, curses.KEY_ENTER}
QUIT_KEYS = {ord("q"), ord("Q")}


def run_tui(stdscr, pages: list) -> None:
    curses.curs_set(0)
    colors = setup_colors()
    idx = 0
    scroll: dict[int, int] = {}

    while True:
        page = pages[idx]
        offset = scroll.get(idx, 0)

        if isinstance(page, TierPage):
            render_tier_page(stdscr, page, idx, len(pages), colors)
        elif isinstance(page, CustomPage):
            max_offset = render_custom_page(stdscr, page, idx, len(pages), colors, offset)
            scroll[idx] = max(0, min(offset, max_offset))
        else:
            max_offset = render_report_page(stdscr, pages, idx, len(pages), colors, offset)
            scroll[idx] = max(0, min(offset, max_offset))

        stdscr.refresh()
        key = stdscr.getch()

        if key in QUIT_KEYS:
            return
        if key == curses.KEY_RESIZE:
            continue
        if key in NEXT_KEYS:
            idx = min(idx + 1, len(pages) - 1)
        elif key in PREV_KEYS:
            idx = max(idx - 1, 0)
        elif key in DOWN_KEYS:
            scroll[idx] = scroll.get(idx, 0) + 1
        elif key in UP_KEYS:
            scroll[idx] = max(scroll.get(idx, 0) - 1, 0)
        elif key in APPLY_KEYS and isinstance(page, CustomPage):
            outcome = page.outcome
            if outcome.detection.status == Status.APPLICABLE and not outcome.applied:
                try:
                    outcome.result = page.customization.apply()
                    outcome.applied = True
                except Exception as exc:  # noqa: BLE001 -- surface any failure in the UI/report
                    outcome.error = str(exc)


def main() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("This tool is an interactive TUI and needs to run in a terminal.", file=sys.stderr)
        sys.exit(1)

    locale.setlocale(locale.LC_ALL, "")  # required for the block-letter title font to render

    pages = build_pages()
    curses.wrapper(run_tui, pages)

    print(f"\n{BANNER}: report")
    print("=" * len(BANNER + ": report"))
    for line in format_report_lines(pages):
        print(line)


if __name__ == "__main__":
    main()
