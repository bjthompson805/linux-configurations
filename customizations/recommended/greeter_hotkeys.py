import shutil
import subprocess
import tempfile
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

GUARD_PATH = Path("/usr/local/bin/thd-guard")
OVERRIDE_PATH = Path("/etc/systemd/system/triggerhappy.service.d/override.conf")
SOCKET_OVERRIDE_PATH = Path("/etc/systemd/system/triggerhappy.socket.d/override.conf")
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

SOCKET_OVERRIDE_CONF = """[Socket]
# Upstream's unit declares ListenStream, but thd/th-cmd's command-socket
# protocol (used by triggerhappy's own udev rule to hand the daemon newly
# added/re-added devices, and by th-cmd in general) is hardcoded to
# AF_UNIX SOCK_DGRAM. A stream socket here means the systemd-activated fd
# handed to thd doesn't match what clients connect with: th-cmd's
# connect() silently fails (it never checks the return value), so every
# hotplug device re-add -- e.g. the ACPI "Video Bus" device SDDM's Xorg
# tears down and recreates each time its greeter (re)starts -- permanently
# loses its trigger until the daemon restarts. Clearing and re-declaring
# as Datagram matches the protocol thd actually speaks.
ListenStream=
ListenDatagram=/run/thd.socket
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
        if shutil.which("brightnessctl") is None:
            return Detection(Status.NOT_APPLICABLE, "brightnessctl is not installed (pacman -S brightnessctl)")
        if shutil.which("amixer") is None:
            return Detection(Status.NOT_APPLICABLE, "alsa-utils is not installed (pacman -S alsa-utils)")

        have_triggerhappy = shutil.which("thd") is not None
        aur_helper = shutil.which("yay") or shutil.which("paru")
        if not have_triggerhappy and aur_helper is None:
            return Detection(
                Status.NOT_APPLICABLE,
                "triggerhappy isn't installed and no AUR helper (yay/paru) was found to install it",
            )

        missing = [
            p
            for p in (GUARD_PATH, OVERRIDE_PATH, SOCKET_OVERRIDE_PATH, BACKLIGHT_PATH, VOLUME_PATH)
            if not p.exists()
        ]
        if have_triggerhappy and not missing:
            return Detection(
                Status.ALREADY_APPLIED,
                "triggerhappy is installed and the guard script, systemd override, and trigger configs are all in place",
            )

        reasons = []
        if not have_triggerhappy:
            reasons.append(f"triggerhappy isn't installed (will build it via {Path(aur_helper).name})")
        if missing:
            reasons.append(f"missing: {', '.join(str(p) for p in missing)}")
        return Detection(
            Status.APPLICABLE,
            "; ".join(reasons),
            value=(aur_helper, have_triggerhappy, missing),
        )

    def explain(self, detection: Detection) -> str:
        aur_helper, have_triggerhappy, _missing = detection.value
        install_note = (
            f"This first builds and installs triggerhappy from the AUR via "
            f"`{Path(aur_helper).name} -S triggerhappy` (it's not in the official "
            "repos) -- expect a small source download/build in addition to the "
            "sudo prompt below.\n\n"
            if not have_triggerhappy
            else ""
        )
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
            f"{install_note}"
            "This installs a root systemd override for triggerhappy (a "
            "hotkey daemon that reads raw evdev key events independent of "
            "any session) plus trigger configs. It also overrides "
            "triggerhappy.socket to listen as a datagram socket instead of "
            "upstream's stream socket -- thd/th-cmd's protocol is hardcoded "
            "to datagram, so with the stock unit any device that gets "
            "hotplugged or re-added after the daemon starts (e.g. the ACPI "
            "\"Video Bus\" device SDDM's own Xorg tears down and recreates "
            "each time its greeter (re)starts) silently and permanently "
            "loses its trigger for the rest of the boot:\n\n"
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
            "Applying this runs several `sudo` commands (possibly the AUR "
            "install, then install root files, systemctl daemon-reload, "
            "enable --now triggerhappy.socket/service) -- expect a sudo "
            "password prompt."
        )

    def apply(self) -> str:
        installed_via = None
        if shutil.which("thd") is None:
            aur_helper = shutil.which("yay") or shutil.which("paru")
            subprocess.run([aur_helper, "-S", "--noconfirm", "triggerhappy"], check=True)
            installed_via = Path(aur_helper).name

        _install_root_file(GUARD_SCRIPT, GUARD_PATH, "755")
        _install_root_file(OVERRIDE_CONF, OVERRIDE_PATH, "644")
        _install_root_file(SOCKET_OVERRIDE_CONF, SOCKET_OVERRIDE_PATH, "644")
        _install_root_file(BACKLIGHT_TRIGGER, BACKLIGHT_PATH, "644")
        _install_root_file(VOLUME_TRIGGER, VOLUME_PATH, "644")
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        # Stop both first (order matters: the socket unit refuses to
        # re-bind while its service is still active, e.g. on a rerun of
        # this customization) so the socket rebinds cleanly with the
        # datagram override before the service can grab it.
        subprocess.run(["sudo", "systemctl", "stop", "triggerhappy.service", "triggerhappy.socket"], check=False)
        subprocess.run(["sudo", "systemctl", "enable", "--now", "triggerhappy.socket"], check=True)
        subprocess.run(["sudo", "systemctl", "enable", "--now", "triggerhappy.service"], check=True)

        prefix = f"Installed triggerhappy via {installed_via}, then installed" if installed_via else "Installed"
        return (
            f"{prefix} thd-guard, the triggerhappy root override, and the "
            "backlight/volume trigger configs; enabled triggerhappy.socket "
            "and triggerhappy.service. Log out to the greeter to test the "
            "brightness/volume/mute keys, then log back in and confirm your "
            "normal Hyprland-side behavior is unaffected."
        )


CUSTOMIZATION = GreeterHotkeys()
