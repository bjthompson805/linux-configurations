import re
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

FISH_CONFIG = Path.home() / ".config" / "fish" / "config.fish"
ALIAS_RE = re.compile(r"^(\s*)alias\s+ls\s+'([^']*)'", re.MULTILINE)
MARKER = "linux-configurations: ls without long listing"


def _swap_long_for_all(command: str) -> str:
    """Replace eza's long-listing flag (-l / --long) with --all (-a)."""
    fixed = []
    for token in command.split():
        if token == "--long":
            token = "--all"
        elif token.startswith("--long="):
            token = "--all=" + token.split("=", 1)[1]
        elif token.startswith("-") and not token.startswith("--") and "l" in token[1:]:
            token = "-" + token[1:].replace("l", "a")
        fixed.append(token)
    return " ".join(fixed)


class EzaLsAlias(Customization):
    id = "eza-ls-alias"
    title = "Stop `ls`'s eza alias from defaulting to long-format"

    def _effective(self) -> tuple[str, Path] | None:
        """The ls alias command that actually wins, and the file that
        defines it (config.fish, unless a later-loaded user.fish overrides
        it there)."""
        if not FISH_CONFIG.exists():
            return None
        config_match = ALIAS_RE.search(FISH_CONFIG.read_text())
        if config_match is None or "eza" not in config_match.group(2):
            return None

        command, source = config_match.group(2), FISH_CONFIG
        user_fish = FISH_CONFIG.with_name("user.fish")
        if user_fish.exists():
            user_match = ALIAS_RE.search(user_fish.read_text())
            if user_match is not None:
                command, source = user_match.group(2), user_fish

        return command, source

    def explain(self, detection: Detection) -> str:
        command, fixed, source = detection.value
        target = util.fish_user_target() or source
        fixed_line = f"alias ls '{fixed}'"
        return (
            f"It appears `ls` is aliased to `{command}` (in {source}), "
            "which turns a plain `ls` into eza's long-listing format "
            "(permissions, owner, size, mtime per line) instead of a normal "
            "multi-column listing. This swaps the -l long-listing flag for "
            "-a (show hidden files) instead, which is what a bare `ls` is "
            "expected to do:\n\n"
            f"{util.indent(fixed_line)}\n\n"
            f"This is written to {target}, so it survives future updates."
        )

    def detect(self) -> Detection:
        effective = self._effective()
        if effective is None:
            return Detection(Status.NOT_APPLICABLE, "ls isn't aliased to eza in ~/.config/fish/config.fish")
        command, source = effective
        fixed = _swap_long_for_all(command)
        if fixed == command:
            return Detection(
                Status.ALREADY_APPLIED,
                f"the effective ls alias (`{command}`, from {source}) doesn't use eza's long listing",
            )
        return Detection(
            Status.APPLICABLE,
            f"ls is aliased to `{command}` (from {source})",
            value=(command, fixed, source),
        )

    def apply(self) -> str:
        command, source = self._effective()
        fixed = _swap_long_for_all(command)
        target = util.fish_user_target()

        text = target.read_text() if target.exists() else ""
        existing = ALIAS_RE.search(text)
        if existing is not None:
            util.backup(target)
            new_text = ALIAS_RE.sub(lambda m: f"{m.group(1)}alias ls '{fixed}'", text, count=1)
            target.write_text(new_text)
        else:
            util.append_block(target, f"alias ls '{fixed}'", MARKER)

        return f"Set alias ls '{fixed}' in {target}."


CUSTOMIZATION = EzaLsAlias()
