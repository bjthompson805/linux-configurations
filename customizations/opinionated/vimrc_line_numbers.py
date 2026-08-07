import re
import shutil
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

VIMRC = Path.home() / ".vimrc"
NUMBER_RE = re.compile(r"^\s*set\s+(nu|number)\b", re.MULTILINE)
NONUMBER_RE = re.compile(r"^\s*set\s+(nonu|nonumber)\b", re.MULTILINE)
TABSTOP_RE = re.compile(r"^\s*set\s+tabstop=(\d+)", re.MULTILINE)
SHIFTWIDTH_RE = re.compile(r"^\s*set\s+shiftwidth=(\d+)", re.MULTILINE)
EXPANDTAB_RE = re.compile(r"^\s*set\s+expandtab\b", re.MULTILINE)
NOEXPANDTAB_RE = re.compile(r"^\s*set\s+noexpandtab\b", re.MULTILINE)
MARKER = "linux-configurations: line numbers + 4-space tabs"

NUMBER_LINE = "set number"
TAB_LINES = ["set tabstop=4", "set shiftwidth=4", "set expandtab"]


class VimrcLineNumbers(Customization):
    id = "vimrc-line-numbers-tabs"
    title = "Add line numbers and 4-space tabs to vim"

    def _missing(self, text: str) -> tuple[list[str], list[str]]:
        """(description bits for explain(), actual lines to append)."""
        bits, lines = [], []
        if NUMBER_RE.search(text) is None or NONUMBER_RE.search(text) is not None:
            bits.append("line numbers (set number)")
            lines.append(NUMBER_LINE)

        tabstop = TABSTOP_RE.search(text)
        shiftwidth = SHIFTWIDTH_RE.search(text)
        expandtab_on = EXPANDTAB_RE.search(text) is not None and NOEXPANDTAB_RE.search(text) is None
        if not (tabstop and tabstop.group(1) == "4" and shiftwidth and shiftwidth.group(1) == "4" and expandtab_on):
            bits.append("4-space tabs (tabstop/shiftwidth=4, expandtab)")
            lines.extend(TAB_LINES)

        return bits, lines

    def explain(self, detection: Detection) -> str:
        bits, lines = detection.value
        block = "\n".join(lines)
        return (
            f"It appears vim is currently missing: {', '.join(bits)}. "
            "This adds:\n\n"
            f"{util.indent(block)}\n\n"
            "`set number` shows line numbers in the left gutter. The tab "
            "settings make the Tab key insert 4 spaces instead of a literal "
            "tab character, and indent/reindent (<<, >>, autoindent) by 4 "
            "spaces as well, so indentation stays consistent regardless of "
            "how another editor or terminal renders a literal tab."
        )

    def detect(self) -> Detection:
        if shutil.which("vim") is None:
            return Detection(Status.NOT_APPLICABLE, "vim doesn't appear to be installed")

        text = VIMRC.read_text() if VIMRC.exists() else ""
        bits, lines = self._missing(text)
        if not bits:
            return Detection(Status.ALREADY_APPLIED, "line numbers and 4-space tabs are already set")
        return Detection(Status.APPLICABLE, f"missing: {', '.join(bits)}", value=(bits, lines))

    def apply(self) -> str:
        text = VIMRC.read_text() if VIMRC.exists() else ""
        _bits, lines = self._missing(text)
        if VIMRC.exists():
            util.backup(VIMRC)
        if text and not text.endswith("\n"):
            text += "\n"
        text += f'\n" {MARKER}\n' + "\n".join(lines) + "\n"
        VIMRC.write_text(text)
        return f"Added {', '.join(lines)} to {VIMRC}."


CUSTOMIZATION = VimrcLineNumbers()
