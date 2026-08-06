import json
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

BRAND_JSON = Path.home() / ".config" / "ryoku" / "brand.json"
ARCH_LOGO = Path("/usr/share/pixmaps/archlinux-logo.svg")


class RyokuBrandArchLogo(Customization):
    id = "ryoku-brand-arch-logo"
    title = "Use the Arch Linux logo as the Ryoku brand mark (Ryoku)"

    def explain(self, detection: Detection) -> str:
        current = detection.value
        state = f"set to {current!r}" if current else "using the default 力 text mark"
        return (
            f"It appears Ryoku's brand mark (~/.config/ryoku/brand.json) is currently "
            f"{state}, rather than the Arch Linux logo shipped at {ARCH_LOGO} (owned by "
            "the `filesystem` package). Applying this sets markImage to that file, so "
            "the pill, launcher, and other branded surfaces show the Arch logo instead "
            "of Ryoku's own mark.\n\n"
            "Note: if Ryoku Settings (Super + ,) is open, save or close it before "
            "applying this -- it rewrites related files on save and could overwrite "
            "this change."
        )

    def _load(self) -> dict:
        return json.loads(BRAND_JSON.read_text())

    def detect(self) -> Detection:
        if not BRAND_JSON.exists():
            return Detection(Status.NOT_APPLICABLE, "Ryoku is not installed (no ~/.config/ryoku/brand.json)")
        if not ARCH_LOGO.exists():
            return Detection(Status.NOT_APPLICABLE, f"{ARCH_LOGO} is not present on this system")
        try:
            data = self._load()
        except (json.JSONDecodeError, OSError):
            return Detection(Status.NOT_APPLICABLE, "brand.json could not be parsed")
        current = data.get("markImage", "")
        if current.removeprefix("file://") == str(ARCH_LOGO):
            return Detection(Status.ALREADY_APPLIED, "markImage is already the Arch Linux logo")
        return Detection(Status.APPLICABLE, f"markImage is currently {current!r}", value=current)

    def apply(self) -> str:
        util.backup(BRAND_JSON)
        data = self._load()
        data["markImage"] = str(ARCH_LOGO)
        BRAND_JSON.write_text(json.dumps(data, indent=4) + "\n")
        return f"Updated {BRAND_JSON} to use {ARCH_LOGO}."


CUSTOMIZATION = RyokuBrandArchLogo()
