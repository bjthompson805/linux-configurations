import re
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

MIMEAPPS = Path.home() / ".config" / "mimeapps.list"
EOG_DESKTOP = Path("/usr/share/applications/org.gnome.eog.desktop")
DESKTOP_ID = "org.gnome.eog.desktop"
SECTION = "[Default Applications]"
SECTION_RE = re.compile(r"^\[.*\]\s*$", re.MULTILINE)

IMAGE_MIMETYPES = [
    "image/avif",
    "image/bmp",
    "image/gif",
    "image/heic",
    "image/jpeg",
    "image/jpg",
    "image/jxl",
    "image/pjpeg",
    "image/png",
    "image/tiff",
    "image/webp",
    "image/x-bmp",
    "image/x-gray",
    "image/x-icb",
    "image/x-ico",
    "image/x-png",
    "image/x-portable-anymap",
    "image/x-portable-bitmap",
    "image/x-portable-graymap",
    "image/x-portable-pixmap",
    "image/x-xbitmap",
    "image/x-xpixmap",
    "image/x-pcx",
    "image/svg+xml",
    "image/svg+xml-compressed",
    "image/vnd.wap.wbmp",
    "image/x-icns",
]


def _current_mapping(text: str) -> dict[str, str]:
    """Parse `key=value` lines that fall within the [Default Applications] section."""
    lines = text.splitlines()
    section_starts = [i for i, line in enumerate(lines) if SECTION_RE.match(line)]
    start = next((i for i in section_starts if lines[i].strip() == SECTION), None)
    if start is None:
        return {}
    end = next((i for i in section_starts if i > start), len(lines))

    mapping = {}
    for line in lines[start + 1:end]:
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        mapping[key.strip()] = value.strip()
    return mapping


def _set_mapping(text: str, updates: dict[str, str]) -> str:
    lines = text.splitlines()
    section_starts = [i for i, line in enumerate(lines) if SECTION_RE.match(line)]
    start = next((i for i in section_starts if lines[i].strip() == SECTION), None)

    if start is None:
        # No [Default Applications] section yet -- add one at the end.
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(SECTION)
        for mimetype, desktop_id in updates.items():
            lines.append(f"{mimetype}={desktop_id}")
        return "\n".join(lines) + "\n"

    end = next((i for i in section_starts if i > start), len(lines))
    remaining = dict(updates)
    for i in range(start + 1, end):
        line = lines[i]
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, _, _ = line.partition("=")
        key = key.strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"

    insert_at = end
    for mimetype, desktop_id in remaining.items():
        lines.insert(insert_at, f"{mimetype}={desktop_id}")
        insert_at += 1

    return "\n".join(lines) + "\n"


class MimeappsEogImages(Customization):
    id = "mimeapps-eog-images"
    title = "Open images with Eye of Gnome instead of the browser"

    def explain(self, detection: Detection) -> str:
        wrong = detection.value
        sample = ", ".join(f"{k} -> {v}" for k, v in list(wrong.items())[:5])
        more = f" (+{len(wrong) - 5} more)" if len(wrong) > 5 else ""
        return (
            f"~/.config/mimeapps.list controls which app opens a file by "
            "mimetype (e.g. what Ryoku's file manager launches on "
            "double-click, or `xdg-open`). It appears some image mimetypes "
            f"aren't mapped to Eye of Gnome yet: {sample}{more}. A common "
            "default here is a browser (e.g. Chrome), which opens images "
            "as a full browser tab instead of a lightweight image viewer.\n\n"
            f"This maps all image mimetypes in [Default Applications] to "
            f"{DESKTOP_ID} ({EOG_DESKTOP})."
        )

    def detect(self) -> Detection:
        if not EOG_DESKTOP.exists():
            return Detection(Status.NOT_APPLICABLE, "Eye of Gnome (eog) is not installed")

        current = _current_mapping(MIMEAPPS.read_text()) if MIMEAPPS.exists() else {}
        wrong = {m: current.get(m, "(unset)") for m in IMAGE_MIMETYPES if current.get(m) != DESKTOP_ID}
        if not wrong:
            return Detection(Status.ALREADY_APPLIED, "all image mimetypes already open with Eye of Gnome")
        return Detection(
            Status.APPLICABLE,
            f"{len(wrong)} image mimetype(s) don't open with Eye of Gnome",
            value=wrong,
        )

    def apply(self) -> str:
        updates = {m: DESKTOP_ID for m in IMAGE_MIMETYPES}
        if MIMEAPPS.exists():
            util.backup(MIMEAPPS)
            text = MIMEAPPS.read_text()
        else:
            text = f"{SECTION}\n"
        MIMEAPPS.write_text(_set_mapping(text, updates))
        return f"Mapped {len(updates)} image mimetypes to {DESKTOP_ID} in {MIMEAPPS}."


CUSTOMIZATION = MimeappsEogImages()
