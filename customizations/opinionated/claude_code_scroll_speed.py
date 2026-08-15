import re
import shutil

from customizations import util
from customizations.base import Customization, Detection, Status

ENV_VAR = "CLAUDE_CODE_SCROLL_SPEED"
# Lines scrolled per wheel/touchpad tick inside claude's own virtual scroll.
# claude itself clamps whatever this is set to at 20.
SPEED = 12
SET_RE = re.compile(r"^\s*set\s+(?:-\S+\s+)*" + ENV_VAR + r"\s+(\S+)", re.MULTILINE)
MARKER = "linux-configurations: speed up scrolling inside the claude CLI"


class ClaudeCodeScrollSpeed(Customization):
    id = "claude-code-scroll-speed"
    title = "Speed up mouse-wheel/touchpad scrolling inside the claude CLI"

    def detect(self) -> Detection:
        if shutil.which("claude") is None:
            return Detection(Status.NOT_APPLICABLE, "claude is not installed")
        target = util.fish_user_target()
        if target is None:
            return Detection(Status.NOT_APPLICABLE, "no fish config found (~/.config/fish)")
        text = target.read_text() if target.exists() else ""

        match = SET_RE.search(text)
        if match is not None:
            return Detection(Status.ALREADY_APPLIED, f"{ENV_VAR} is already set to {match.group(1)} in {target}")
        return Detection(Status.APPLICABLE, f"{ENV_VAR} is unset", value=target)

    def explain(self, detection: Detection) -> str:
        target = detection.value
        return (
            "The claude CLI (an Ink-based TUI) enables xterm mouse-tracking "
            r"(the \e[?1000h / \e[?1006h escape sequences) so it can handle "
            "its own scrolling of the conversation transcript, rather than "
            "relying on kitty's native scrollback pager. Because of that, "
            "kitty's wheel_scroll_multiplier / touch_scroll_multiplier "
            "settings never reach it -- kitty just forwards one raw wheel "
            "event per physical tick, and claude decides internally how "
            "many lines that moves. On this terminal (kitty, not VS Code, "
            "not Windows Terminal, not xterm.js) claude's own built-in "
            "heuristic defaults that to 1 line per tick, which is what's "
            "showing up as slow scrolling specifically inside claude, even "
            "though kitty's own scrollback elsewhere is already 3x faster.\n\n"
            f"claude reads its own override for this from the {ENV_VAR} "
            "environment variable (any positive number, capped at 20 by "
            f"claude itself). This exports it in {target}:\n\n"
            f"{util.indent(f'set -gx {ENV_VAR} {SPEED}')}\n\n"
            "Trade-off: this only speeds up scrolling inside claude's own "
            "transcript view -- kitty's native scrollback for every other "
            "program is unaffected (that's the separate kitty-scroll-speed "
            "customization) -- and it only takes effect in new claude "
            "sessions started after a fresh shell picks up the exported "
            "variable."
        )

    def apply(self) -> str:
        target = util.fish_user_target()
        util.append_block(target, f"set -gx {ENV_VAR} {SPEED}", MARKER)
        return (
            f"Exported {ENV_VAR}={SPEED} in {target}. Open a new shell (or "
            f"`source {target}`) and start a new claude session to pick it up."
        )


CUSTOMIZATION = ClaudeCodeScrollSpeed()
