import shutil

from customizations import util
from customizations.base import Customization, Detection, Status

BLOCK = """hl.on("hyprland.start", function()
    hl.exec_cmd("wl-clip-persist --clipboard regular")
end)"""
MARKER = "linux-configurations: wl-clip-persist"

class WlClipPersist(Customization):
    id = "wl-clip-persist"
    title = "Keep clipboard contents after programs exit"

    def explain(self, detection: Detection) -> str:
        return (
            "Wayland's default clipboard behavior drops copied text when the "
            "program it was copied from is closed. wl-clip-persist fixes this "
            "by briefly holding onto the clipboard data in the background.\n\n"
            "This customization appends a startup hook to your Hyprland user "
            "config to run wl-clip-persist on login:\n\n"
            f"{util.indent(BLOCK)}\n"
        )

    def detect(self) -> Detection:
        if not util.is_hyprland_active():
            return Detection(Status.NOT_APPLICABLE, "Hyprland is not installed/running")
        target = util.hypr_lua_target()
        if target is None:
            return Detection(Status.NOT_APPLICABLE, "no Hyprland Lua config found")
        
        if util.hypr_lua_contains("wl-clip-persist"):
            return Detection(Status.ALREADY_APPLIED, "wl-clip-persist is already configured in Hyprland")
            
        if shutil.which("wl-clip-persist") is None:
            return Detection(
                Status.NOT_APPLICABLE, 
                "wl-clip-persist is not installed (run `sudo pacman -S wl-clip-persist`)"
            )
            
        return Detection(Status.APPLICABLE, "wl-clip-persist is installed but not started in Hyprland")

    def apply(self) -> str:
        target = util.hypr_lua_target()
        util.append_lua(target, BLOCK, MARKER)
        return f"Added wl-clip-persist autostart to {target}. It will run on your next login."

CUSTOMIZATION = WlClipPersist()
