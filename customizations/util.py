"""Small shared helpers for reading/writing config that customizations touch."""

from __future__ import annotations

import datetime
import json
import shutil
import subprocess
from pathlib import Path

HYPR_DIR = Path.home() / ".config" / "hypr"
FISH_DIR = Path.home() / ".config" / "fish"


def indent(text: str, prefix: str = "  ") -> str:
    """Prefix every line of `text` (not just the first) for display in an explanation."""
    return "\n".join(prefix + line for line in text.splitlines())


def backup(path: Path) -> Path:
    """Copy `path` aside with a timestamp suffix before modifying it in place."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = path.with_name(f"{path.name}.bak.{stamp}")
    shutil.copy2(path, dest)
    return dest


def is_hyprland_active() -> bool:
    return shutil.which("hyprctl") is not None


def hyprctl_int_option(option: str) -> int | None:
    if not is_hyprland_active():
        return None
    try:
        r = subprocess.run(
            ["hyprctl", "-j", "getoption", option],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout).get("int")
    except ValueError:
        return None


def hyprctl_bool_option(option: str) -> bool | None:
    if not is_hyprland_active():
        return None
    try:
        r = subprocess.run(
            ["hyprctl", "-j", "getoption", option],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout).get("bool")
    except ValueError:
        return None


def hyprctl_has_touchpad() -> bool:
    """Whether hyprctl reports a pointer device whose name looks like a touchpad."""
    if not is_hyprland_active():
        return False
    try:
        r = subprocess.run(
            ["hyprctl", "-j", "devices"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return False
    if r.returncode != 0:
        return False
    try:
        data = json.loads(r.stdout)
    except ValueError:
        return False
    return any("touchpad" in m.get("name", "").lower() for m in data.get("mice", []))


def hypr_lua_files() -> list[Path]:
    if not HYPR_DIR.is_dir():
        return []
    return sorted(HYPR_DIR.rglob("*.lua"))


def hypr_lua_contains(needle: str) -> bool:
    for f in hypr_lua_files():
        try:
            if needle in f.read_text():
                return True
        except OSError:
            continue
    return False


def hypr_lua_target() -> Path | None:
    """Where new Hyprland Lua config should be appended.

    Prefers ~/.config/hypr/user.lua: on a Ryoku-managed system it is
    documented as the file that loads last and is never touched by updates,
    which makes it the safe place to add or override binds. Falls back to
    hyprland.lua itself for a plain Hyprland 0.55+ Lua config that has no
    such convention.
    """
    if not HYPR_DIR.is_dir():
        return None
    user_lua = HYPR_DIR / "user.lua"
    if user_lua.exists():
        return user_lua
    hyprland_lua = HYPR_DIR / "hyprland.lua"
    if hyprland_lua.exists():
        return hyprland_lua
    return None


def fish_user_target() -> Path | None:
    """Where new fish config should be appended.

    Prefers ~/.config/fish/user.fish: on a Ryoku-managed system it is
    documented as the file that loads last and is never touched by updates,
    which makes it the safe place to add or override settings. Falls back to
    config.fish itself for a plain fish setup with no such convention.
    """
    if not FISH_DIR.is_dir():
        return None
    user_fish = FISH_DIR / "user.fish"
    if user_fish.exists():
        return user_fish
    config_fish = FISH_DIR / "config.fish"
    if config_fish.exists():
        return config_fish
    return None


def append_block(path: Path, block: str, marker: str, comment: str = "#") -> None:
    """Append `block` to `path`, guarded by `marker` so re-runs are a no-op."""
    text = path.read_text() if path.exists() else ""
    if marker in text:
        return
    if path.exists():
        backup(path)
    with path.open("a") as f:
        if text and not text.endswith("\n"):
            f.write("\n")
        f.write(f"\n{comment} {marker}\n{block}\n")


def append_lua(path: Path, block: str, marker: str) -> None:
    append_block(path, block, marker, comment="--")
