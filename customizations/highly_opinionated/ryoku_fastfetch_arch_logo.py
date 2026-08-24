import json
import shutil
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

FASTFETCH_DIR = Path.home() / ".config" / "fastfetch"
CONFIG_JSONC = FASTFETCH_DIR / "config.jsonc"
RYOKU_EMBLEM = FASTFETCH_DIR / "fastfetch-emblem.png"
SYSTEM_ARCH_LOGO = Path("/usr/share/pixmaps/archlinux-logo.png")
LOCAL_ARCH_LOGO = FASTFETCH_DIR / "archlinux-logo.png"
LOCAL_ARCH_LOGO_SOURCE = "~/.config/fastfetch/archlinux-logo.png"


class RyokuFastfetchArchLogo(Customization):
    id = "ryoku-fastfetch-arch-logo"
    title = "Show the Arch Linux logo in fastfetch instead of the Ryoku emblem (Ryoku)"

    def explain(self, detection: Detection) -> str:
        current = detection.value
        return (
            f"It appears fastfetch's logo (~/.config/fastfetch/config.jsonc) is "
            f"currently {current!r}, rather than the Arch Linux logo. Applying "
            f"this copies {SYSTEM_ARCH_LOGO} (owned by the `filesystem` package) "
            f"to {LOCAL_ARCH_LOGO} -- kitty-direct needs a raster image and a "
            "self-contained copy survives the original moving -- and points "
            "logo.source at it, so the fastfetch greeting shows the Arch logo "
            "instead of Ryoku's own emblem. The original emblem "
            f"({RYOKU_EMBLEM}) is left in place, so reverting is just pointing "
            "logo.source back."
        )

    def _load(self) -> dict:
        return json.loads(CONFIG_JSONC.read_text())

    def detect(self) -> Detection:
        if not RYOKU_EMBLEM.exists():
            return Detection(Status.NOT_APPLICABLE, "Ryoku's branded fastfetch is not set up (no fastfetch-emblem.png)")
        if not CONFIG_JSONC.exists():
            return Detection(Status.NOT_APPLICABLE, "no ~/.config/fastfetch/config.jsonc")
        if not SYSTEM_ARCH_LOGO.exists():
            return Detection(Status.NOT_APPLICABLE, f"{SYSTEM_ARCH_LOGO} is not present on this system")
        try:
            data = self._load()
        except (json.JSONDecodeError, OSError):
            return Detection(Status.NOT_APPLICABLE, "config.jsonc could not be parsed (comments in it?)")
        current = data.get("logo", {}).get("source", "")
        if current.removeprefix("file://") == LOCAL_ARCH_LOGO_SOURCE and LOCAL_ARCH_LOGO.exists():
            return Detection(Status.ALREADY_APPLIED, "logo.source is already the Arch Linux logo")
        return Detection(Status.APPLICABLE, f"logo.source is currently {current!r}", value=current)

    def apply(self) -> str:
        shutil.copy2(SYSTEM_ARCH_LOGO, LOCAL_ARCH_LOGO)
        util.backup(CONFIG_JSONC)
        data = self._load()
        data.setdefault("logo", {})["source"] = LOCAL_ARCH_LOGO_SOURCE
        CONFIG_JSONC.write_text(json.dumps(data, indent=2) + "\n")
        return f"Copied {SYSTEM_ARCH_LOGO} to {LOCAL_ARCH_LOGO} and updated {CONFIG_JSONC}."


CUSTOMIZATION = RyokuFastfetchArchLogo()
