import re
import shutil
import subprocess
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

OVERRIDE_DIR = Path.home() / ".config" / "systemd" / "user" / "onedrive.service.d"
OVERRIDE_PATH = OVERRIDE_DIR / "override.conf"

_EXEC_START_RE = re.compile(r"^ExecStart=(.*)$", re.MULTILINE)


def _cat_onedrive_unit() -> str | None:
    """The fully merged unit text (base file + any drop-ins), or None if there's no such unit."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "cat", "onedrive.service"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _effective_monitor_exec_start(unit_text: str) -> str | None:
    """The ExecStart command that runs monitor mode, after applying drop-in resets.

    An `ExecStart=` line with an empty value clears every ExecStart directive seen
    so far (systemd's override mechanism) -- so this has to replay the directives
    in file order, not just grep for the last non-empty one.
    """
    exec_starts: list[str] = []
    for value in _EXEC_START_RE.findall(unit_text):
        value = value.strip()
        if not value:
            exec_starts = []
        else:
            exec_starts.append(value)
    for cmd in reversed(exec_starts):
        if "--monitor" in cmd:
            return cmd
    return None


def _service_active() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", "onedrive.service"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


class OnedriveDisableNotifications(Customization):
    id = "onedrive-disable-notifications"
    title = "Silence desktop notifications from the OneDrive monitor service"

    def detect(self) -> Detection:
        if shutil.which("onedrive") is None:
            return Detection(Status.NOT_APPLICABLE, "onedrive is not installed")
        unit_text = _cat_onedrive_unit()
        if unit_text is None:
            return Detection(Status.NOT_APPLICABLE, "no onedrive.service systemd user unit found")
        monitor_cmd = _effective_monitor_exec_start(unit_text)
        if monitor_cmd is None:
            return Detection(
                Status.NOT_APPLICABLE,
                "onedrive.service's ExecStart does not run monitor mode",
            )
        if "--disable-notifications" in monitor_cmd:
            return Detection(
                Status.ALREADY_APPLIED,
                f"onedrive.service already runs `{monitor_cmd}`",
            )
        return Detection(
            Status.APPLICABLE,
            f"onedrive.service runs `{monitor_cmd}` with no --disable-notifications flag",
            value=monitor_cmd,
        )

    def explain(self, detection: Detection) -> str:
        return (
            f"It appears onedrive.service currently runs `{detection.value}`, "
            "with no --disable-notifications flag.\n\n"
            "In monitor mode the onedrive client raises a desktop notification "
            "for sync events -- files uploaded/downloaded, conflicts, errors -- "
            "every time they happen in the background. --disable-notifications "
            "turns those off so the monitor syncs silently.\n\n"
            f"This adds a systemd drop-in at {OVERRIDE_PATH} that overrides "
            "ExecStart to append the flag, rather than editing the package-"
            "managed unit file in /usr/lib/systemd/user/ directly -- so a "
            "future `onedrive` package update won't silently revert it.\n\n"
            "Trade-off: you stop getting a toast when a sync fails (expired "
            "auth, a full disk, a file conflict) -- you'd need to check "
            "`journalctl --user -u onedrive.service` to notice."
        )

    def apply(self) -> str:
        unit_text = _cat_onedrive_unit()
        monitor_cmd = _effective_monitor_exec_start(unit_text)
        new_cmd = f"{monitor_cmd} --disable-notifications"

        OVERRIDE_DIR.mkdir(parents=True, exist_ok=True)
        if OVERRIDE_PATH.exists():
            util.backup(OVERRIDE_PATH)
        OVERRIDE_PATH.write_text(f"[Service]\nExecStart=\nExecStart={new_cmd}\n")

        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        restarted = _service_active()
        if restarted:
            subprocess.run(["systemctl", "--user", "restart", "onedrive.service"], check=True)

        message = f"Wrote {OVERRIDE_PATH} overriding ExecStart to `{new_cmd}`."
        if restarted:
            message += " Restarted onedrive.service to pick it up immediately."
        return message


CUSTOMIZATION = OnedriveDisableNotifications()
