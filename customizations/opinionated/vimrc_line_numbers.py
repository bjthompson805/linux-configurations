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
DEFAULTS_BLOCK = (
    "\" linux-configurations: keep vim defaults (syntax highlighting, filetype\n"
    "\" detection, etc.) that only auto-load when there's no ~/.vimrc\n"
    "unlet! g:skip_defaults_vim\n"
    "source $VIMRUNTIME/defaults.vim\n"
)


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
        bits, lines, creating_fresh = detection.value
        block = "\n".join(lines)
        extra = ""
        if creating_fresh:
            extra = (
                "\n\nYou don't have a ~/.vimrc yet, so vim currently auto-loads "
                "$VIMRUNTIME/defaults.vim on its own -- that's what turns on "
                "syntax highlighting and filetype detection. Creating a "
                "~/.vimrc, even a minimal one, stops that auto-load, so this "
                "also adds an explicit `source $VIMRUNTIME/defaults.vim` first "
                "so you don't lose syntax highlighting."
            )
        return (
            f"It appears vim is currently missing: {', '.join(bits)}. "
            "This adds:\n\n"
            f"{util.indent(block)}\n\n"
            "`set number` shows line numbers in the left gutter. The tab "
            "settings make the Tab key insert 4 spaces instead of a literal "
            "tab character, and indent/reindent (<<, >>, autoindent) by 4 "
            "spaces as well, so indentation stays consistent regardless of "
            "how another editor or terminal renders a literal tab."
            f"{extra}"
        )

    def detect(self) -> Detection:
        if shutil.which("vim") is None:
            return Detection(Status.NOT_APPLICABLE, "vim doesn't appear to be installed")

        existed = VIMRC.exists()
        text = VIMRC.read_text() if existed else ""
        bits, lines = self._missing(text)
        if not bits:
            return Detection(Status.ALREADY_APPLIED, "line numbers and 4-space tabs are already set")
        return Detection(Status.APPLICABLE, f"missing: {', '.join(bits)}", value=(bits, lines, not existed))

    def apply(self) -> str:
        existed = VIMRC.exists()
        text = VIMRC.read_text() if existed else ""
        _bits, lines = self._missing(text)
        if existed:
            util.backup(VIMRC)
        if text and not text.endswith("\n"):
            text += "\n"
        if not existed:
            text += DEFAULTS_BLOCK + "\n"
        text += f'\n" {MARKER}\n' + "\n".join(lines) + "\n"
        VIMRC.write_text(text)
        msg = f"Added {', '.join(lines)} to {VIMRC}."
        if not existed:
            msg += (
                " Also added `source $VIMRUNTIME/defaults.vim` (with "
                "`unlet! g:skip_defaults_vim`), since creating ~/.vimrc "
                "disables vim's automatic loading of it -- this keeps syntax "
                "highlighting and filetype detection working."
            )
        return msg


CUSTOMIZATION = VimrcLineNumbers()
