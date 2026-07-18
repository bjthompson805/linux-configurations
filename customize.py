#!/usr/bin/env python3
"""Interactive, generic Hyprland/Arch Linux customization tool.

Walks three tiers of customizations in order:

  1. Suggested          -- bug fixes and changes almost anyone would want
  2. Opinionated        -- changes the author likes, others might not
  3. Highly opinionated -- changes specific to the author's own setup,
                            reviewed only if the user opts in

Each customization is a self-contained module under customizations/<tier>/
exposing a module-level CUSTOMIZATION instance. See README.md for how to add
a new one.
"""

import importlib
import pkgutil
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from customizations.base import Status  # noqa: E402

BANNER = "linux-configurations: Interactively apply Hyprland/Arch Linux customizations"

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_LIGHT_BLUE = "\x1b[38;2;135;206;250m"
_LIGHT_PURPLE = "\x1b[38;2;177;156;217m"
_DARK_YELLOW = "\x1b[38;2;184;134;11m"


def _h1(text: str) -> str:
    rule = "─" * len(text)
    if sys.stdout.isatty():
        return f"{_BOLD}{_LIGHT_BLUE}{rule}\n{text}\n{rule}{_RESET}"
    return f"{rule}\n{text}\n{rule}"


def _h2(text: str) -> str:
    if sys.stdout.isatty():
        return f"{_BOLD}{_LIGHT_PURPLE}{text}{_RESET}"
    return text


def _result(text: str) -> str:
    if sys.stdout.isatty():
        return f"{_BOLD}{_DARK_YELLOW}{text}{_RESET}"
    return text


def _bold(text: str) -> str:
    if sys.stdout.isatty():
        return f"{_BOLD}{text}{_RESET}"
    return text


class StatusBar:
    """A single status line pinned to the bottom of the terminal.

    Uses the classic scroll-region trick (DECSTBM): the scrolling region is
    shrunk to exclude the last row, so normal output scrolls above it while
    that row stays put. A no-op (via `enabled`) when stdout isn't a tty, so
    piped/redirected output is unaffected.
    """

    def __init__(self):
        self.enabled = sys.stdout.isatty()
        self._rows = 0

    def __enter__(self):
        if self.enabled:
            rows = shutil.get_terminal_size(fallback=(80, 24)).lines
            if rows < 3:
                self.enabled = False
            else:
                self._rows = rows
                sys.stdout.write(f"\x1b[1;{rows - 1}r")  # reserve the last row
                sys.stdout.write(f"\x1b[{rows - 1};1H")  # cursor to top of the region
                sys.stdout.flush()
        return self

    def set(self, text: str) -> None:
        if not self.enabled:
            return
        styled = f"{_BOLD}{_LIGHT_PURPLE}{text}{_RESET}"
        sys.stdout.write("\x1b7")  # save cursor position
        sys.stdout.write(f"\x1b[{self._rows};1H\x1b[2K{styled}")
        sys.stdout.write("\x1b8")  # restore cursor position
        sys.stdout.flush()

    def __exit__(self, exc_type, exc, tb):
        if self.enabled:
            sys.stdout.write("\x1b[r")  # reset scroll region to the full screen
            sys.stdout.write(f"\x1b[{self._rows};1H\x1b[2K")  # clear the bar's row
            sys.stdout.flush()
        return False


def bar_text(label: str, total: int, remaining: int, width: int = 24) -> str:
    if total == 0:
        return f"{label}: nothing to review"
    done = total - remaining
    filled = int(width * done / total)
    bar = "█" * filled + "░" * (width - filled)
    return f"{label}  [{bar}]  {remaining} remaining"


TIERS = [
    (
        "suggested",
        "Suggested",
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


def prompt_yes_no(question: str) -> bool:
    while True:
        answer = input(f"{question} [y/n] ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer y or n.")


def run_group(tier_specs, label, status_bar, log):
    """Run one or more tiers as a single progress-bar phase.

    Detection runs for every customization in the group up front, so the bar
    can show an accurate remaining count from the start; suggested +
    opinionated are passed together (they never gate on an opt-in prompt, so
    they read as one phase), highly-opinionated runs alone as its own phase.
    """
    tiers = [(tier_label, blurb, load_tier(pkg_name)) for pkg_name, tier_label, blurb in tier_specs]
    detected = [
        (tier_label, blurb, [(c, c.detect()) for c in items])
        for tier_label, blurb, items in tiers
    ]

    total = sum(
        1
        for _, _, items in detected
        for _, detection in items
        if detection.status == Status.APPLICABLE
    )
    remaining = total
    status_bar.set(bar_text(label, total, remaining))

    for tier_label, blurb, items in detected:
        print(f"\n{_h2(f'=== {tier_label} customizations ===')}")
        print(blurb)
        if not items:
            print("(none yet)")
            continue

        for customization, detection in items:
            if detection.status == Status.NOT_APPLICABLE:
                reason = detection.reason or "not applicable"
                print(f"  - {customization.title}: skipped ({reason})")
                log["skipped"].append(customization.title)
                continue

            if detection.status == Status.ALREADY_APPLIED:
                suffix = f" ({detection.reason})" if detection.reason else ""
                print(f"  - {customization.title}: {_bold('already applied')}{suffix}")
                log["already"].append(customization.title)
                continue

            print(f"\n{customization.title}")
            print("-" * len(customization.title))
            print(customization.explain(detection))
            if prompt_yes_no("\nApply this?"):
                result = customization.apply()
                print(_result(f"-> {result}"))
                log["applied"].append(customization.title)
            else:
                print("-> skipped")
                log["declined"].append(customization.title)

            remaining -= 1
            status_bar.set(bar_text(label, total, remaining))


def print_summary(log):
    print("\n=== Summary ===")
    print(f"Applied: {len(log['applied'])}")
    for title in log["applied"]:
        print(f"  - {title}")
    print(f"Declined: {len(log['declined'])}")
    for title in log["declined"]:
        print(f"  - {title}")
    print(f"Already applied: {len(log['already'])}")
    print(f"Not applicable: {len(log['skipped'])}")


def main():
    print(_h1(BANNER))
    log = {"applied": [], "skipped": [], "already": [], "declined": []}

    with StatusBar() as status_bar:
        run_group(TIERS[0:2], "Suggested & Opinionated", status_bar, log)

        if prompt_yes_no("\nReview highly-opinionated customizations too?"):
            run_group(TIERS[2:3], "Highly opinionated", status_bar, log)

        print_summary(log)


if __name__ == "__main__":
    main()
