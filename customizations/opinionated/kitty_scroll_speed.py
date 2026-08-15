import re
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

KITTY_CONF = Path.home() / ".config" / "kitty" / "kitty.conf"

# kitty's own built-in defaults (confirmed against /usr/share/doc/kitty/kitty.conf
# for the installed version), used when a setting isn't present anywhere in the file.
DEFAULT_WHEEL_MULTIPLIER = 5.0
DEFAULT_TOUCH_MULTIPLIER = 1.0
SPEEDUP = 3

WHEEL_RE = re.compile(r"^\s*wheel_scroll_multiplier\s+(\S+)", re.MULTILINE)
TOUCH_RE = re.compile(r"^\s*touch_scroll_multiplier\s+(\S+)", re.MULTILINE)
MARKER = "linux-configurations: 3x kitty scroll speed"


def _fmt(value: float) -> str:
    return f"{value:g}"


class KittyScrollSpeed(Customization):
    id = "kitty-scroll-speed"
    title = "Triple kitty's scrolling speed"

    def _last_value(self, text: str, regex: re.Pattern, default: float) -> float:
        # kitty applies directives in file order, so a later assignment wins;
        # take the last match to get the setting's actual effective value.
        matches = regex.findall(text)
        if not matches:
            return default
        try:
            return float(matches[-1])
        except ValueError:
            return default

    def detect(self) -> Detection:
        if not KITTY_CONF.exists():
            return Detection(Status.NOT_APPLICABLE, "no kitty config found (~/.config/kitty/kitty.conf)")
        text = KITTY_CONF.read_text()

        if MARKER in text:
            return Detection(Status.ALREADY_APPLIED, "kitty scroll speed was already tripled by this tool")

        wheel = self._last_value(text, WHEEL_RE, DEFAULT_WHEEL_MULTIPLIER)
        touch = self._last_value(text, TOUCH_RE, DEFAULT_TOUCH_MULTIPLIER)
        has_touchpad = util.hyprctl_has_touchpad()
        reason = f"effective wheel_scroll_multiplier is {_fmt(wheel)}, touch_scroll_multiplier is {_fmt(touch)}"
        return Detection(Status.APPLICABLE, reason, value=(wheel, touch, has_touchpad))

    def explain(self, detection: Detection) -> str:
        wheel, touch, has_touchpad = detection.value
        new_wheel, new_touch = wheel * SPEEDUP, touch * SPEEDUP
        touchpad_note = (
            " Hyprland reports a touchpad on this system, so that setting isn't just theoretical here."
            if has_touchpad
            else ""
        )
        return (
            "kitty splits scroll speed across two separate settings depending "
            "on the input device: wheel_scroll_multiplier for a physical "
            "mouse wheel's discrete clicks, and touch_scroll_multiplier for "
            "the smooth, high-precision scroll events a touchpad sends. "
            "kitty's own docs call this out as mattering specifically on "
            "Wayland (which this system runs, via Hyprland) -- "
            "wheel_scroll_multiplier alone would leave touchpad scrolling "
            f"untouched.{touchpad_note} This triples both, from their "
            f"current effective values ({_fmt(wheel)} -> {_fmt(new_wheel)} "
            f"for the wheel, {_fmt(touch)} -> {_fmt(new_touch)} for the "
            "touchpad):\n\n"
            f"{util.indent(f'wheel_scroll_multiplier {_fmt(new_wheel)}')}\n"
            f"{util.indent(f'touch_scroll_multiplier {_fmt(new_touch)}')}\n\n"
            "These are appended at the end of the file, after the existing "
            "globinclude user.conf line -- consistent with the other "
            "overrides already placed there -- so they win even if "
            "user.conf sets its own value.\n\n"
            "Trade-off: scrolling becomes much more sensitive -- a light "
            "wheel flick or touchpad swipe will jump three times as far "
            "through scrollback as before."
        )

    def apply(self) -> str:
        util.backup(KITTY_CONF)
        text = KITTY_CONF.read_text()
        wheel = self._last_value(text, WHEEL_RE, DEFAULT_WHEEL_MULTIPLIER) * SPEEDUP
        touch = self._last_value(text, TOUCH_RE, DEFAULT_TOUCH_MULTIPLIER) * SPEEDUP

        text = (
            text.rstrip("\n")
            + f"\n\n# {MARKER}"
            + f"\nwheel_scroll_multiplier {_fmt(wheel)}"
            + f"\ntouch_scroll_multiplier {_fmt(touch)}\n"
        )
        KITTY_CONF.write_text(text)
        return (
            f"In {KITTY_CONF}: set wheel_scroll_multiplier to {_fmt(wheel)} "
            f"and touch_scroll_multiplier to {_fmt(touch)} (3x their "
            "previous effective values). Recent kitty versions auto-reload "
            "their config on save; if yours doesn't, restart kitty to see "
            "the change."
        )


CUSTOMIZATION = KittyScrollSpeed()
