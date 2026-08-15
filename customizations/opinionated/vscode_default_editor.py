import re
import shutil
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

MIMEAPPS = Path.home() / ".config" / "mimeapps.list"
CODE_DESKTOP_PATHS = [
    Path("/usr/share/applications/code.desktop"),
    Path.home() / ".local" / "share" / "applications" / "code.desktop",
]
CODE_DESKTOP_ID = "code.desktop"
SECTION = "[Default Applications]"
SECTION_RE = re.compile(r"^\[.*\]\s*$", re.MULTILINE)

# Ryoku ships all of these pointed at ryoku-nvim.desktop. text/markdown and
# text/html are deliberately left out -- those are commonly pointed at a
# dedicated markdown viewer or a browser rather than a code editor, and
# clobbering a user's own override there isn't this customization's business.
TEXT_MIMETYPES = [
    "text/plain",
    "application/json",
    "text/xml",
    "application/xml",
    "text/x-shellscript",
    "application/x-shellscript",
    "text/x-python",
    "text/x-lua",
    "text/css",
    "text/x-csrc",
    "text/x-chdr",
    "text/x-c++src",
    "text/x-go",
    "application/toml",
    "text/x-toml",
    "application/x-yaml",
    "text/yaml",
]

FISH_MARKER = "linux-configurations: VS Code as EDITOR/VISUAL"
FISH_BLOCK = "set -gx EDITOR code-wait\nset -gx VISUAL code-wait"

WRAPPER = Path.home() / ".local" / "bin" / "code-wait"
WRAPPER_CONTENT = '#!/bin/sh\nexec code --wait "$@"\n'


def _current_mapping(text: str) -> dict[str, str]:
    """Parse `key=value` lines that fall within the [Default Applications] section."""
    lines = text.splitlines()
    section_starts = [i for i, line in enumerate(lines) if SECTION_RE.match(line)]
    start = next((i for i in section_starts if lines[i].strip() == SECTION), None)
    if start is None:
        return {}
    end = next((i for i in section_starts if i > start), len(lines))

    mapping = {}
    for line in lines[start + 1:end]:
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        mapping[key.strip()] = value.strip()
    return mapping


def _set_mapping(text: str, updates: dict[str, str]) -> str:
    lines = text.splitlines()
    section_starts = [i for i, line in enumerate(lines) if SECTION_RE.match(line)]
    start = next((i for i in section_starts if lines[i].strip() == SECTION), None)

    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(SECTION)
        for mimetype, desktop_id in updates.items():
            lines.append(f"{mimetype}={desktop_id}")
        return "\n".join(lines) + "\n"

    end = next((i for i in section_starts if i > start), len(lines))
    remaining = dict(updates)
    for i in range(start + 1, end):
        line = lines[i]
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, _, _ = line.partition("=")
        key = key.strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"

    insert_at = end
    for mimetype, desktop_id in remaining.items():
        lines.insert(insert_at, f"{mimetype}={desktop_id}")
        insert_at += 1

    return "\n".join(lines) + "\n"


class VscodeDefaultEditor(Customization):
    id = "vscode-default-editor"
    title = "Make VS Code the default text/code editor (instead of neovim)"

    def detect(self) -> Detection:
        if shutil.which("code") is None:
            return Detection(Status.NOT_APPLICABLE, "the `code` CLI is not installed")
        if not any(p.exists() for p in CODE_DESKTOP_PATHS):
            return Detection(Status.NOT_APPLICABLE, "no code.desktop entry found on the application search path")

        fish_target = util.fish_user_target()
        if fish_target is None:
            return Detection(Status.NOT_APPLICABLE, "no fish config found (~/.config/fish)")

        fish_text = fish_target.read_text() if fish_target.exists() else ""
        shell_missing = FISH_MARKER not in fish_text
        wrapper_missing = not (WRAPPER.exists() and WRAPPER.read_text() == WRAPPER_CONTENT)

        current = _current_mapping(MIMEAPPS.read_text()) if MIMEAPPS.exists() else {}
        wrong = {m: current.get(m, "(unset)") for m in TEXT_MIMETYPES if current.get(m) != CODE_DESKTOP_ID}

        if not shell_missing and not wrapper_missing and not wrong:
            return Detection(Status.ALREADY_APPLIED, "EDITOR/VISUAL and the text mimetypes already point at VS Code")

        reason_bits = []
        if shell_missing or wrapper_missing:
            reason_bits.append("EDITOR/VISUAL aren't pointed at VS Code")
        if wrong:
            reason_bits.append(f"{len(wrong)} text mimetype(s) aren't mapped to {CODE_DESKTOP_ID}")
        return Detection(
            Status.APPLICABLE,
            ", ".join(reason_bits),
            value=(shell_missing, wrapper_missing, wrong, fish_target),
        )

    def explain(self, detection: Detection) -> str:
        shell_missing, wrapper_missing, wrong, fish_target = detection.value
        parts = [
            "Ryoku defaults both the shell's $EDITOR/$VISUAL and the "
            "desktop's file-open mimetype map to neovim (ryoku-nvim.desktop). "
            "This switches both to VS Code instead."
        ]
        if shell_missing or wrapper_missing:
            parts.append(
                f"Writes {WRAPPER}:\n\n"
                f"{util.indent(WRAPPER_CONTENT.rstrip())}\n\n"
                "and, in "
                f"{fish_target}, appends (so it wins over ryoku's own "
                f"`set -gx EDITOR nvim` earlier in the file, without editing "
                f"ryoku's lines in place):\n\n"
                f"{util.indent(FISH_BLOCK)}\n\n"
                "$EDITOR/$VISUAL point at the wrapper rather than the literal "
                "string \"code --wait\": several consumers of these variables "
                "(git and other shell-based tools) re-split the value on "
                "whitespace themselves, but not all do -- anything that "
                "spawns $EDITOR directly as a single executable (e.g. a TUI's "
                "own click-to-open-in-editor handler) will fail to find a "
                "binary literally named \"code --wait\" and silently no-op. "
                "The wrapper keeps $EDITOR a single token for every consumer, "
                "while still adding VS Code's `--wait` flag so callers that "
                "block on the editor exiting (git commit, crontab -e, "
                "sudoedit) work correctly."
            )
        if wrong:
            sample = ", ".join(f"{k} -> {v}" for k, v in list(wrong.items())[:5])
            more = f" (+{len(wrong) - 5} more)" if len(wrong) > 5 else ""
            parts.append(
                f"In {MIMEAPPS}, remaps {len(wrong)} text/code mimetype(s) "
                f"currently not pointed at {CODE_DESKTOP_ID}: {sample}{more}. "
                "text/markdown and text/html are deliberately left alone -- "
                "those are commonly pointed at a markdown viewer or a "
                "browser instead, and this customization only owns the "
                "code-editor mimetypes."
            )
        return "\n\n".join(parts)

    def apply(self) -> str:
        # Re-detect fresh state rather than trusting a possibly-stale Detection.
        fish_target = util.fish_user_target()
        fish_text = fish_target.read_text() if fish_target.exists() else ""
        shell_missing = FISH_MARKER not in fish_text
        wrapper_missing = not (WRAPPER.exists() and WRAPPER.read_text() == WRAPPER_CONTENT)

        current = _current_mapping(MIMEAPPS.read_text()) if MIMEAPPS.exists() else {}
        wrong = {m: current.get(m, "(unset)") for m in TEXT_MIMETYPES if current.get(m) != CODE_DESKTOP_ID}

        results = []
        if wrapper_missing:
            WRAPPER.parent.mkdir(parents=True, exist_ok=True)
            if WRAPPER.exists():
                util.backup(WRAPPER)
            WRAPPER.write_text(WRAPPER_CONTENT)
            WRAPPER.chmod(0o755)
            results.append(f"wrote {WRAPPER}")

        if shell_missing:
            util.append_block(fish_target, FISH_BLOCK, FISH_MARKER)
            results.append(f"exported EDITOR/VISUAL as code-wait in {fish_target}")

        if wrong:
            updates = {m: CODE_DESKTOP_ID for m in wrong}
            if MIMEAPPS.exists():
                util.backup(MIMEAPPS)
                text = MIMEAPPS.read_text()
            else:
                text = f"{SECTION}\n"
            MIMEAPPS.write_text(_set_mapping(text, updates))
            results.append(f"mapped {len(updates)} text mimetype(s) to {CODE_DESKTOP_ID} in {MIMEAPPS}")

        return "; ".join(results).capitalize() + ". Open a new shell to pick up EDITOR/VISUAL."


CUSTOMIZATION = VscodeDefaultEditor()
