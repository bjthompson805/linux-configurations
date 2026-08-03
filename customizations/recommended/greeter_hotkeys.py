import shutil
import subprocess
import tempfile
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

GUARD_PATH = Path("/usr/local/bin/thd-guard")
OVERRIDE_PATH = Path("/etc/systemd/system/triggerhappy.service.d/override.conf")
BACKLIGHT_PATH = Path("/etc/triggerhappy/triggers.d/backlight.conf")
VOLUME_PATH = Path("/etc/triggerhappy/triggers.d/volume.conf")

GUARD_SCRIPT = """#!/bin/sh
# Only run the given command when no real user session owns seat0 right
# now (i.e. at the SDDM greeter or a bare console). Hyprland's own hotkey
# binds already handle brightness/volume whenever you're actually logged
# in - including while locked, since hyprlock just overlays the still-live
# compositor. Without this guard, triggerhappy and Hyprland would both
# react to the same physical key and double-adjust.
active=$(loginctl show-seat seat0 -p ActiveSession --value 2>/dev/null)
if [ -n "$active" ]; then
    class=$(loginctl show-session "$active" -p Class --value 2>/dev/null)
    [ "$class" = "user" ] && exit 0
fi
exec "$@"
"""

OVERRIDE_CONF = """[Service]
# Drop the upstream default's "--user nobody": our trigger commands write
# directly to /sys/class/backlight/*/brightness (root:root 0644) and the
# ALSA hw mixer, both of which need root. thd itself must stay root for
# the whole process lifetime, not just while opening input devices.
ExecStart=
ExecStart=/usr/sbin/thd --triggers /etc/triggerhappy/triggers.d/ --socket /run/thd.socket --deviceglob /dev/input/event*
"""

BACKLIGHT_TRIGGER = """KEY_BRIGHTNESSUP\t1\t/usr/local/bin/thd-guard /usr/bin/brightnessctl set 5%+
KEY_BRIGHTNESSUP\t2\t/usr/local/bin/thd-guard /usr/bin/brightnessctl set 5%+
KEY_BRIGHTNESSDOWN\t1\t/usr/local/bin/thd-guard /usr/bin/brightnessctl set 5%-
KEY_BRIGHTNESSDOWN\t2\t/usr/local/bin/thd-guard /usr/bin/brightnessctl set 5%-
"""

VOLUME_TRIGGER = """KEY_VOLUMEUP\t1\t/usr/local/bin/thd-guard /usr/bin/amixer -q set Master 5%+
KEY_VOLUMEUP\t2\t/usr/local/bin/thd-guard /usr/bin/amixer -q set Master 5%+
KEY_VOLUMEDOWN\t1\t/usr/local/bin/thd-guard /usr/bin/amixer -q set Master 5%-
KEY_VOLUMEDOWN\t2\t/usr/local/bin/thd-guard /usr/bin/amixer -q set Master 5%-
KEY_MUTE\t1\t/usr/local/bin/thd-guard /usr/bin/amixer -q set Master toggle
"""


def _install_root_file(content: str, dest: Path, mode: str) -> None:
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(content)
        tmp = f.name
    try:
        subprocess.run(["sudo", "install", "-Dm" + mode, tmp, str(dest)], check=True)
    finally:
        Path(tmp).unlink(missing_ok=True)


class GreeterHotkeys(Customization):
    id = "greeter-hotkeys"
    title = "Make brightness/volume/mute keys work at the SDDM greeter"

    def detect(self) -> Detection:
        if not util.is_hyprland_active():
            return Detection(Status.NOT_APPLICABLE, "Hyprland is not installed/running")
        if shutil.which("thd") is None:
            return Detection(
                Status.NOT_APPLICABLE,
                "triggerhappy is not installed (AUR only: yay -S triggerhappy)",
            )
        if shutil.which("brightnessctl") is None:
            return Detection(Status.NOT_APPLICABLE, "brightnessctl is not installed (pacman -S brightnessctl)")
        if shutil.which("amixer") is None:
            return Detection(Status.NOT_APPLICABLE, "alsa-utils is not installed (pacman -S alsa-utils)")

        missing = [p for p in (GUARD_PATH, OVERRIDE_PATH, BACKLIGHT_PATH, VOLUME_PATH) if not p.exists()]
        if not missing:
            return Detection(Status.ALREADY_APPLIED, "guard script, systemd override, and trigger configs are all in place")
        return Detection(
            Status.APPLICABLE,
            f"missing: {', '.join(str(p) for p in missing)}",
            value=missing,
        )

    def explain(self, detection: Detection) -> str:
        return (
            f"It appears {detection.reason}. Brightness/volume/mute keys only "
            "work today because Hyprland itself binds them (XF86MonBrightnessUp/"
            "Down to brightnessctl, XF86Audio* to wpctl) -- confirmed on this "
            "kind of setup that brightnessctl only succeeds via systemd-"
            "logind's D-Bus SetBrightness fallback for your active session "
            "rather than a direct sysfs write, and wpctl only reaches "
            "PipeWire/WirePlumber, which are user-session services. Neither "
            "exists at the SDDM greeter (its own bare X11/Wayland server "
            "with no keybinding daemon) or a bare console, so the same keys "
            "do nothing there -- it's not a permissions problem, nothing is "
            "listening.\n\n"
            "This installs a root systemd override for triggerhappy (a "
            "hotkey daemon that reads raw evdev key events independent of "
            "any session) plus trigger configs:\n\n"
            f"{util.indent(BACKLIGHT_TRIGGER.rstrip())}\n"
            f"{util.indent(VOLUME_TRIGGER.rstrip())}\n\n"
            "Backlight goes through brightnessctl; volume goes through the "
            "ALSA hw mixer directly (amixer), since PipeWire isn't running "
            "pre-login. Both commands go through /usr/local/bin/thd-guard "
            "first, which checks loginctl's active session on seat0 and "
            "no-ops whenever it's class 'user' (i.e. you're actually logged "
            "into Hyprland, locked or not) so Hyprland's own binds keep "
            "exclusive control there and the two don't double-adjust the "
            "same key press. It only acts at the greeter, a bare console, "
            "or when nothing is logged in.\n\n"
            "Applying this runs several `sudo` commands (install root files, "
            "systemctl daemon-reload, enable --now triggerhappy.socket/"
            "service) -- expect a sudo password prompt."
        )

    def apply(self) -> str:
        _install_root_file(GUARD_SCRIPT, GUARD_PATH, "755")
        _install_root_file(OVERRIDE_CONF, OVERRIDE_PATH, "644")
        _install_root_file(BACKLIGHT_TRIGGER, BACKLIGHT_PATH, "644")
        _install_root_file(VOLUME_TRIGGER, VOLUME_PATH, "644")
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["sudo", "systemctl", "enable", "--now", "triggerhappy.socket"], check=True)
        subprocess.run(["sudo", "systemctl", "enable", "--now", "triggerhappy.service"], check=True)
        return (
            "Installed thd-guard, the triggerhappy root override, and the "
            "backlight/volume trigger configs; enabled triggerhappy.socket "
            "and triggerhappy.service. Log out to the greeter to test the "
            "brightness/volume/mute keys, then log back in and confirm your "
            "normal Hyprland-side behavior is unaffected."
        )


CUSTOMIZATION = GreeterHotkeys()
