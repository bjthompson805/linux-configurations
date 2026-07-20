import json
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

PERF_JSON = Path.home() / ".config" / "ryoku" / "performance.json"
KEY = "unloadLauncherWhenIdle"


class RyokuUnloadLauncherIdle(Customization):
    id = "ryoku-unload-launcher-idle"
    title = "Unload the launcher process when idle (Ryoku)"

    def explain(self, detection: Detection) -> str:
        return (
            f"It appears {KEY} is currently set to false in Ryoku's "
            "performance settings (~/.config/ryoku/performance.json). This "
            "controls whether the quickshell launcher process stays resident "
            "in the background. Turning it on makes the launcher process "
            "exit after 60 seconds of not being used, at the cost of a "
            "brief extra delay the next time you open it while it "
            "restarts.\n\n"
            "While resident and idle, the launcher process still wakes "
            "roughly 60 times a second, which keeps the CPU from settling "
            "into a deeper idle state. Unloading it after idle removes "
            "those wakeups, letting the CPU idle more deeply and "
            "meaningfully reducing power consumption.\n\n"
            "Note: if Ryoku Settings (Super + ,) is open, save or close it "
            "before applying this -- it rewrites related files on save and "
            "could overwrite this change."
        )

    def _load(self) -> dict:
        return json.loads(PERF_JSON.read_text())

    def detect(self) -> Detection:
        if not PERF_JSON.exists():
            return Detection(Status.NOT_APPLICABLE, "Ryoku is not installed (no ~/.config/ryoku/performance.json)")
        try:
            data = self._load()
        except (json.JSONDecodeError, OSError):
            return Detection(Status.NOT_APPLICABLE, "performance.json could not be parsed")
        if data.get(KEY) is True:
            return Detection(Status.ALREADY_APPLIED, f"{KEY} is already true")
        return Detection(Status.APPLICABLE, f"{KEY} is currently false")

    def apply(self) -> str:
        util.backup(PERF_JSON)
        data = self._load()
        data[KEY] = True
        PERF_JSON.write_text(json.dumps(data, indent=4) + "\n")
        return f"Updated {PERF_JSON}."


CUSTOMIZATION = RyokuUnloadLauncherIdle()
