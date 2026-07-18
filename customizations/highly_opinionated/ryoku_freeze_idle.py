import json
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

PERF_JSON = Path.home() / ".config" / "ryoku" / "performance.json"
KEYS = ("freezePillWhenIdle", "freezeVisualizerWhenIdle")


class RyokuFreezeIdle(Customization):
    id = "ryoku-freeze-idle"
    title = "Freeze the pill and visualizer when idle (Ryoku)"

    def explain(self, detection: Detection) -> str:
        settings = " and ".join(detection.value)
        verb = "is" if len(detection.value) == 1 else "are"
        return (
            f"It appears {settings} {verb} currently set to false in Ryoku's "
            "performance settings (~/.config/ryoku/performance.json). These "
            "control whether the status pill and the audio visualizer keep "
            "animating while the system is idle. Turning them on stops that "
            "animation work while idle, which saves battery at the cost of "
            "those elements not animating during idle.\n\n"
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
        missing = [k for k in KEYS if data.get(k) is not True]
        if not missing:
            return Detection(Status.ALREADY_APPLIED, "both settings are already true")
        return Detection(Status.APPLICABLE, f"currently false: {', '.join(missing)}", value=missing)

    def apply(self) -> str:
        util.backup(PERF_JSON)
        data = self._load()
        for key in KEYS:
            data[key] = True
        PERF_JSON.write_text(json.dumps(data, indent=4) + "\n")
        return f"Updated {PERF_JSON}."


CUSTOMIZATION = RyokuFreezeIdle()
