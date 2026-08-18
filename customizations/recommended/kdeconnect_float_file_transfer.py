import shutil

from customizations import util
from customizations.base import Customization, Detection, Status

BLOCK = (
    'hl.window_rule({\n'
    '    name   = "float-kdeconnect-file-transfer",\n'
    '    match  = { class = "org.kde.kdeconnect.daemon" },\n'
    '    float  = true,\n'
    '    size   = { 628, 324 },\n'
    '    center = true,\n'
    '})'
)
MARKER = "linux-configurations: float KDE Connect file transfer window"
KDECONNECT_CLASS = "org.kde.kdeconnect.daemon"


class KdeconnectFloatFileTransfer(Customization):
    id = "kdeconnect-float-file-transfer"
    title = "Float KDE Connect's file-transfer window instead of tiling it"

    def explain(self, detection: Detection) -> str:
        return (
            "When KDE Connect's daemon is sending or receiving a file, it "
            f"pops up its own small progress window under the class "
            f"{KDECONNECT_CLASS}. With no window rule for it, Hyprland's "
            "tiling logic gets to decide what happens to that window on "
            "open, which can shove it into your layout as a tiled window "
            "instead of leaving it as the small floating dialog it's meant "
            "to be.\n\n"
            "This adds an explicit rule pinning it to float and centering "
            "it at a fixed 628x324 -- the size the window itself currently "
            "requests -- so it always opens the same small dialog "
            "regardless of Hyprland's own size-hint heuristics or whatever "
            "layout you're in at the time:\n\n"
            f"{util.indent(BLOCK)}"
        )

    def detect(self) -> Detection:
        if not util.is_hyprland_active():
            return Detection(Status.NOT_APPLICABLE, "Hyprland is not installed/running")
        if shutil.which("kdeconnectd") is None:
            return Detection(Status.NOT_APPLICABLE, "KDE Connect is not installed")
        target = util.hypr_lua_target()
        if target is None:
            return Detection(Status.NOT_APPLICABLE, "no Hyprland Lua config found")
        if util.hypr_lua_contains(KDECONNECT_CLASS):
            return Detection(
                Status.ALREADY_APPLIED,
                f"a window rule already references {KDECONNECT_CLASS}",
            )
        return Detection(
            Status.APPLICABLE,
            f"no window rule for KDE Connect's file-transfer window (class {KDECONNECT_CLASS}) was found",
        )

    def apply(self) -> str:
        target = util.hypr_lua_target()
        util.append_lua(target, BLOCK, MARKER)
        return f"Added a float rule for {KDECONNECT_CLASS} to {target}. Run `hyprctl reload` to pick it up."


CUSTOMIZATION = KdeconnectFloatFileTransfer()
