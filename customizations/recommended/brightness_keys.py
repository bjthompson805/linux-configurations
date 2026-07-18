import shutil
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

BLOCK = (
    'hl.bind("XF86MonBrightnessUp",   hl.dsp.exec_cmd("brightnessctl set 5%+"), '
    "{ locked = true, repeating = true })\n"
    'hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("brightnessctl set 5%-"), '
    "{ locked = true, repeating = true })"
)
MARKER = "linux-configurations: backlight keys"


class BrightnessKeys(Customization):
    id = "brightness-keys"
    title = "Bind laptop backlight keys in Hyprland"

    def explain(self, detection: Detection) -> str:
        return (
            "It appears your brightness keys (XF86MonBrightnessUp / "
            "XF86MonBrightnessDown) aren't bound to anything in Hyprland, so "
            "pressing them does nothing. This adds keybinds using "
            "brightnessctl, following the same pattern Hyprland's own "
            "volume-key binds use -- locked so it still works from the lock "
            "screen, repeating so holding the key ramps brightness smoothly:\n\n"
            f"{util.indent(BLOCK)}\n\n"
            "This is appended to your Hyprland Lua config's user-override "
            "file, so it survives future updates."
        )

    def detect(self) -> Detection:
        if not util.is_hyprland_active():
            return Detection(Status.NOT_APPLICABLE, "Hyprland is not installed/running")
        target = util.hypr_lua_target()
        if target is None:
            return Detection(Status.NOT_APPLICABLE, "no Hyprland Lua config found")
        backlight = Path("/sys/class/backlight")
        if not backlight.is_dir() or not any(backlight.iterdir()):
            return Detection(
                Status.NOT_APPLICABLE,
                "no backlight device found (not a laptop, or brightness isn't OS-controlled)",
            )
        if util.hypr_lua_contains("XF86MonBrightnessUp"):
            return Detection(Status.ALREADY_APPLIED, "a bind for XF86MonBrightnessUp already exists")
        if shutil.which("brightnessctl") is None:
            return Detection(Status.NOT_APPLICABLE, "brightnessctl is not installed (pacman -S brightnessctl)")
        return Detection(Status.APPLICABLE, "no bind for XF86MonBrightnessUp/Down found")

    def apply(self) -> str:
        target = util.hypr_lua_target()
        util.append_lua(target, BLOCK, MARKER)
        return f"Added backlight keybinds to {target}. Run `hyprctl reload` to pick it up."


CUSTOMIZATION = BrightnessKeys()
