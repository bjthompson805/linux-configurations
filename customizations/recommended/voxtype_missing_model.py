import re
import shutil
import subprocess
from pathlib import Path

from customizations.base import Customization, Detection, Status

CONFIG_PATH = Path.home() / ".config" / "voxtype" / "config.toml"
MODELS_DIR = Path.home() / ".local" / "share" / "voxtype" / "models"

_WHISPER_SECTION_RE = re.compile(r"^\[whisper\](.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL)
_MODEL_LINE_RE = re.compile(r'^\s*model\s*=\s*"([^"]+)"', re.MULTILINE)


def _configured_whisper_model(text: str) -> str | None:
    """Pull `model = "..."` out of the `[whisper]` section, without a TOML dependency."""
    section = _WHISPER_SECTION_RE.search(text)
    if not section:
        return None
    match = _MODEL_LINE_RE.search(section.group(1))
    return match.group(1) if match else None


def _voxtype_service_active() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", "voxtype.service"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


class VoxtypeMissingModel(Customization):
    id = "voxtype-missing-model"
    title = "Download voxtype's configured Whisper model if it's missing"

    def detect(self) -> Detection:
        if shutil.which("voxtype") is None:
            return Detection(Status.NOT_APPLICABLE, "voxtype is not installed")
        if not CONFIG_PATH.exists():
            return Detection(Status.NOT_APPLICABLE, "no voxtype config found at ~/.config/voxtype/config.toml")
        model = _configured_whisper_model(CONFIG_PATH.read_text())
        if not model:
            return Detection(Status.NOT_APPLICABLE, "voxtype's config has no [whisper] model configured")
        model_path = MODELS_DIR / f"ggml-{model}.bin"
        if model_path.exists():
            return Detection(Status.ALREADY_APPLIED, f"the configured Whisper model '{model}' is already downloaded")
        return Detection(
            Status.APPLICABLE,
            f"voxtype is configured to use Whisper model '{model}', but {model_path} doesn't exist on disk",
            value=(model, _voxtype_service_active()),
        )

    def explain(self, detection: Detection) -> str:
        model, service_active = detection.value
        loop_note = (
            "voxtype.service is currently active on this system; Ryoku's default drop-in "
            "sets `Restart=always` with `StartLimitIntervalSec=0`, so a missing model "
            "doesn't fail loudly once -- it makes the daemon exit immediately and "
            "relaunch every couple seconds, forever, with no indication anything is "
            "wrong short of reading the journal."
            if service_active else
            "Running `voxtype daemon` directly (or via a non-resilient systemd unit) "
            "would just fail once with the same underlying error."
        )
        return (
            f"It appears {detection.reason}. {loop_note}\n\n"
            f"This runs `voxtype setup --download --model {model}`, which fetches "
            f"ggml-{model}.bin from Hugging Face (ggerganov/whisper.cpp) -- for a "
            "'base.en'-sized model that's roughly 148MB; larger models (small/medium/"
            "large-v3) run from several hundred MB up to ~3GB, so confirm you're fine "
            "with the transfer before applying, especially on a metered connection.\n\n"
            "If voxtype.service is currently active, this also restarts it afterward "
            "so the daemon picks up the model immediately instead of waiting for its "
            "next crash-restart cycle."
        )

    def apply(self) -> str:
        model = _configured_whisper_model(CONFIG_PATH.read_text())
        subprocess.run(["voxtype", "setup", "--download", "--model", model], check=True)

        restart = _voxtype_service_active()
        if restart:
            subprocess.run(["systemctl", "--user", "restart", "voxtype.service"], check=True)

        message = f"Downloaded the '{model}' Whisper model via `voxtype setup --download`."
        if restart:
            message += " Restarted voxtype.service so the daemon picks it up immediately."
        return message


CUSTOMIZATION = VoxtypeMissingModel()
