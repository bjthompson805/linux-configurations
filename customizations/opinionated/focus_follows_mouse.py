from customizations import util
from customizations.base import Customization, Detection, Status

BLOCK = "hl.config({ input = { follow_mouse = 1 } })"
MARKER = "linux-configurations: hover-to-focus"


class FocusFollowsMouse(Customization):
    id = "focus-follows-mouse"
    title = "Focus windows on hover instead of click"

    def explain(self, detection: Detection) -> str:
        return (
            f"It appears your Hyprland input:follow_mouse setting is "
            f"currently {detection.value}, which detaches focus from the "
            "pointer until you click a window.\n\n"
            "Setting it to 1 restores Hyprland's default hover-to-focus "
            "behavior: the window under the cursor gets keyboard focus as "
            "soon as the mouse moves onto it, no click needed.\n\n"
            "Trade-off: a non-default value like this is often chosen "
            "specifically to stop a newly opened window from losing keyboard "
            "focus to whatever window the cursor happens to already be "
            "resting on. Switching to 1 brings that quirk back -- a window "
            "you just opened (e.g. via a keybind) can lose focus to whatever "
            "is under the cursor, until you move the mouse over the new "
            "window yourself.\n\n"
            f"  {BLOCK}"
        )

    def detect(self) -> Detection:
        if not util.is_hyprland_active():
            return Detection(Status.NOT_APPLICABLE, "Hyprland is not installed/running")
        target = util.hypr_lua_target()
        if target is None:
            return Detection(Status.NOT_APPLICABLE, "no Hyprland Lua config found")
        value = util.hyprctl_int_option("input:follow_mouse")
        if value is None:
            return Detection(Status.NOT_APPLICABLE, "could not read input:follow_mouse from hyprctl")
        if value == 1:
            return Detection(Status.ALREADY_APPLIED, "input:follow_mouse is already 1 (hover-to-focus)")
        return Detection(Status.APPLICABLE, f"input:follow_mouse is currently {value}", value=value)

    def apply(self) -> str:
        target = util.hypr_lua_target()
        util.append_lua(target, BLOCK, MARKER)
        return f"Set follow_mouse = 1 in {target}. Run `hyprctl reload` to pick it up."


CUSTOMIZATION = FocusFollowsMouse()
