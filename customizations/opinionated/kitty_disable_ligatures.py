import re
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

KITTY_CONF = Path.home() / ".config" / "kitty" / "kitty.conf"
DISABLE_LIGATURES_RE = re.compile(r"^(\s*)disable_ligatures\s+(\S+)", re.MULTILINE)
FONT_FAMILY_RE = re.compile(r"^\s*font_family\s+(.+)$", re.MULTILINE)


class KittyDisableLigatures(Customization):
    id = "kitty-disable-ligatures"
    title = "Disable kitty's font ligatures"

    def _current_setting(self, text: str) -> str | None:
        match = DISABLE_LIGATURES_RE.search(text)
        return match.group(2) if match else None

    def _font_family(self, text: str) -> str | None:
        match = FONT_FAMILY_RE.search(text)
        return match.group(1).strip() if match else None

    def explain(self, detection: Detection) -> str:
        setting, font = detection.value
        current = setting or "never (kitty's default -- ligatures always render)"
        font_note = f" ({font})" if font else ""
        return (
            f"disable_ligatures is currently {current}. Ligatures substitute "
            "a run of characters for a single combined glyph purely for "
            f"display (e.g. '->' becomes an arrow). The substitution happens "
            f"live as you type, and your font{font_note} defines a 3-character "
            "ligature for repeated asterisks (asterisk_asterisk_asterisk.liga, "
            "seemingly meant for Markdown's '***'). Typing a 3rd '*' anywhere "
            "-- a shell glob, a sudo/pwfeedback password prompt echoing "
            "'*' per keystroke, anything -- makes kitty reshape the last "
            "three characters into that combined glyph mid-keystroke, which "
            "visibly nudges the character before it for a frame before it "
            "settles. Confirmed live on this system: 'disable_ligatures "
            "cursor' does NOT fix it (the cursor has already moved past the "
            "ligature's span by the time it forms) -- only 'always' does. "
            "This sets:\n\n"
            f"{util.indent('disable_ligatures always')}\n\n"
            "Trade-off: this turns off ALL ligatures in kitty, not just this "
            "one glyph -- arrows, !=, etc. render as separate characters "
            "everywhere, not just while typing."
        )

    def detect(self) -> Detection:
        if not KITTY_CONF.exists():
            return Detection(Status.NOT_APPLICABLE, "no kitty config found (~/.config/kitty/kitty.conf)")
        text = KITTY_CONF.read_text()
        setting = self._current_setting(text)

        if setting == "always":
            return Detection(Status.ALREADY_APPLIED, "disable_ligatures is already set to always")

        reason = f"disable_ligatures is currently {setting or 'unset (defaults to never)'}"
        return Detection(Status.APPLICABLE, reason, value=(setting, self._font_family(text)))

    def apply(self) -> str:
        util.backup(KITTY_CONF)
        text = KITTY_CONF.read_text()

        if DISABLE_LIGATURES_RE.search(text):
            text = DISABLE_LIGATURES_RE.sub(lambda m: f"{m.group(1)}disable_ligatures always", text, count=1)
        elif FONT_FAMILY_RE.search(text):
            text = FONT_FAMILY_RE.sub(lambda m: f"{m.group(0)}\ndisable_ligatures always", text, count=1)
        else:
            text = (
                text.rstrip("\n")
                + "\n\n# linux-configurations: stop ligature substitution from jittering repeated glyphs mid-keystroke"
                + "\ndisable_ligatures always\n"
            )

        KITTY_CONF.write_text(text)
        return (
            f"In {KITTY_CONF}: set disable_ligatures to always. Recent "
            "kitty versions auto-reload their config on save; if yours "
            "doesn't, restart kitty to see the change."
        )


CUSTOMIZATION = KittyDisableLigatures()
