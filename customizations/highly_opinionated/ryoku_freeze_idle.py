import json
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

PERF_JSON = Path.home() / ".config" / "ryoku" / "performance.json"
KEYS = ("freezePillWhenIdle", "freezeVisualizerWhenIdle", "unloadVisualizerWhenSilent")


class RyokuFreezeIdle(Customization):
    id = "ryoku-freeze-idle-unload-silent"
    title = "Freeze the pill, freeze the visualizer when idle, and unload it when silent (Ryoku)"

    def explain(self, detection: Detection) -> str:
        settings = " and ".join(detection.value) if len(detection.value) <= 2 else ", ".join(detection.value[:-1]) + f", and {detection.value[-1]}"
        verb = "is" if len(detection.value) == 1 else "are"
        return (
            f"It appears {settings} {verb} currently set to false in Ryoku's "
            "performance settings (~/.config/ryoku/performance.json). These "
            "control whether the status pill and the audio visualizer keep "
            "animating while the system is idle, and whether the visualizer "
            "is unloaded entirely when there's no audio playing. Turning "
            "them on stops that animation and rendering work while idle or "
            "silent, which saves battery at the cost of those elements not "
            "animating during idle and the visualizer taking a moment to "
            "reload when audio resumes.\n\n"
            "Note: if Ryoku Settings (Super + ,) is open, save or close it "
            "before applying this -- it rewrites related files on save and "
            "could overwrite this change."
        )

    def _load(self) -> dict:
        if not PERF_JSON.exists():
            return {}
        return json.loads(PERF_JSON.read_text())

    def detect(self) -> Detection:
        if not util.is_ryoku_installed():
            return Detection(Status.NOT_APPLICABLE, "Ryoku is not installed (no `ryoku` on PATH)")
        try:
            data = self._load()
        except (json.JSONDecodeError, OSError):
            return Detection(Status.NOT_APPLICABLE, "performance.json could not be parsed")
        missing = [k for k in KEYS if data.get(k) is not True]
        if not missing:
            return Detection(Status.ALREADY_APPLIED, "all settings are already true")
        return Detection(Status.APPLICABLE, f"currently false: {', '.join(missing)}", value=missing)

    def apply(self) -> str:
        if PERF_JSON.exists():
            util.backup(PERF_JSON)
        data = self._load()
        for key in KEYS:
            data[key] = True
        PERF_JSON.parent.mkdir(parents=True, exist_ok=True)
        PERF_JSON.write_text(json.dumps(data, indent=4) + "\n")
        return f"Updated {PERF_JSON}."


CUSTOMIZATION = RyokuFreezeIdle()
