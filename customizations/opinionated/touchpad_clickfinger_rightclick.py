from customizations import util
from customizations.base import Customization, Detection, Status

BLOCK = "hl.config({ input = { touchpad = { clickfinger_behavior = true } } })"
MARKER = "linux-configurations: two-finger right-click only"


class TouchpadClickfingerRightClick(Customization):
    id = "touchpad-clickfinger-rightclick"
    title = "Require a two-finger tap/click for touchpad right-click"

    def explain(self, detection: Detection) -> str:
        return (
            "It appears your Hyprland input:touchpad:clickfinger_behavior "
            "setting is currently false, which means libinput's default "
            "\"button areas\" click method is in effect: a single-finger "
            "click (or tap) in the bottom-right corner of the touchpad "
            "registers as a right-click, and bottom-left/middle registers "
            "as a left-click. Resting or dragging a finger through that "
            "corner is enough to trigger an accidental right-click.\n\n"
            "Setting clickfinger_behavior to true switches to libinput's "
            "\"clickfinger\" method instead: the click/tap is classified by "
            "how many fingers are down, not where on the pad they land. One "
            "finger is always a left-click, two fingers is always a "
            "right-click, three is a middle-click -- so a right-click only "
            "fires from a deliberate two-finger tap or two-finger click, "
            "anywhere on the pad.\n\n"
            f"  {BLOCK}\n\n"
            "Trade-off: the bottom-right-corner single-finger right-click "
            "stops working entirely -- you must use two fingers. It also "
            "changes three-finger clicks/taps to middle-click if that "
            "wasn't already the case."
        )

    def detect(self) -> Detection:
        if not util.is_hyprland_active():
            return Detection(Status.NOT_APPLICABLE, "Hyprland is not installed/running")
        target = util.hypr_lua_target()
        if target is None:
            return Detection(Status.NOT_APPLICABLE, "no Hyprland Lua config found")
        if not util.hyprctl_has_touchpad():
            return Detection(Status.NOT_APPLICABLE, "no touchpad device detected")
        value = util.hyprctl_bool_option("input:touchpad:clickfinger_behavior")
        if value is None:
            return Detection(
                Status.NOT_APPLICABLE,
                "could not read input:touchpad:clickfinger_behavior from hyprctl",
            )
        if value:
            return Detection(
                Status.ALREADY_APPLIED,
                "input:touchpad:clickfinger_behavior is already true "
                "(right-click already requires two fingers)",
            )
        return Detection(
            Status.APPLICABLE,
            "input:touchpad:clickfinger_behavior is currently false",
            value=value,
        )

    def apply(self) -> str:
        target = util.hypr_lua_target()
        util.append_lua(target, BLOCK, MARKER)
        return (
            f"Set touchpad clickfinger_behavior = true in {target}. Run "
            "`hyprctl reload` to pick it up."
        )


CUSTOMIZATION = TouchpadClickfingerRightClick()
