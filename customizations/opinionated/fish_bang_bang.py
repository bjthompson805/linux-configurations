import shutil

from customizations import util
from customizations.base import Customization, Detection, Status

FUNCTIONS_DIR = util.FISH_DIR / "functions"
CONF_D_DIR = util.FISH_DIR / "conf.d"

HISTORY_PREVIOUS_COMMAND = FUNCTIONS_DIR / "__history_previous_command.fish"
HISTORY_PREVIOUS_COMMAND_ARGS = FUNCTIONS_DIR / "__history_previous_command_arguments.fish"
KEY_BINDINGS = CONF_D_DIR / "plugin-bang-bang.fish"

HISTORY_PREVIOUS_COMMAND_CONTENT = """function __history_previous_command
  switch (commandline -t)
  case "!"
    commandline -t $history[1]; commandline -f repaint
  case "*"
    commandline -i !
  end
end
"""

HISTORY_PREVIOUS_COMMAND_ARGS_CONTENT = """function __history_previous_command_arguments
  switch (commandline -t)
  case "!"
    commandline -t ""
    commandline -f history-token-search-backward
  case "*"
    commandline -i '$'
  end
end
"""

KEY_BINDINGS_CONTENT = """function _plugin-bang-bang_key_bindings --on-variable fish_key_bindings
    bind --erase !
    bind --erase '$'
    switch "$fish_key_bindings"
    case 'fish_default_key_bindings'
        bind --mode default ! __history_previous_command
        bind --mode default '$' __history_previous_command_arguments
    case 'fish_vi_key_bindings' 'fish_hybrid_key_bindings'
        bind --mode insert ! __history_previous_command
        bind --mode insert '$' __history_previous_command_arguments
    end
end

function _plugin-bang-bang_uninstall --on-event plugin-bang-bang_uninstall
    bind --erase !
    bind --erase '$'
    functions --erase _plugin-bang-bang_uninstall
end

_plugin-bang-bang_key_bindings"""

FILES = {
    HISTORY_PREVIOUS_COMMAND: HISTORY_PREVIOUS_COMMAND_CONTENT,
    HISTORY_PREVIOUS_COMMAND_ARGS: HISTORY_PREVIOUS_COMMAND_ARGS_CONTENT,
    KEY_BINDINGS: KEY_BINDINGS_CONTENT,
}


class FishBangBang(Customization):
    id = "fish-bang-bang"
    title = "Add bash-style !! / !$ history expansion to fish"

    def explain(self, detection: Detection) -> str:
        missing = detection.value
        return (
            "It appears fish doesn't expand bash-style history bangs -- "
            "typing `!!` (previous command) or `!$` (previous command's "
            "last argument) inserts them literally instead of substituting "
            "history, since fish has no built-in equivalent. This vendors "
            "the (tiny, 3-file) oh-my-fish/plugin-bang-bang plugin directly "
            f"into your fish config rather than pulling in fisher as a "
            f"dependency: {', '.join(str(p) for p in missing)}.\n\n"
            "It binds `!` and `$` in whichever key-binding mode you're "
            "using (default or vi-insert) to expand in place: `!` alone "
            "becomes the previous command, `!<text>` still types literally "
            "(e.g. for `!=`), and `$` alone becomes the previous command's "
            "last argument (repeatable, walking further back each time)."
        )

    def detect(self) -> Detection:
        if shutil.which("fish") is None:
            return Detection(Status.NOT_APPLICABLE, "fish is not installed")
        if not util.FISH_DIR.is_dir():
            return Detection(Status.NOT_APPLICABLE, "no ~/.config/fish directory found")

        missing = [path for path, content in FILES.items() if not (path.exists() and path.read_text() == content)]
        if not missing:
            return Detection(Status.ALREADY_APPLIED, "the bang-bang key bindings are already installed")
        return Detection(
            Status.APPLICABLE,
            f"missing or out of date: {', '.join(str(p) for p in missing)}",
            value=missing,
        )

    def apply(self) -> str:
        FUNCTIONS_DIR.mkdir(parents=True, exist_ok=True)
        CONF_D_DIR.mkdir(parents=True, exist_ok=True)
        written = []
        for path, content in FILES.items():
            if path.exists():
                if path.read_text() == content:
                    continue
                util.backup(path)
            path.write_text(content)
            written.append(path)
        return (
            f"Wrote {', '.join(str(p) for p in written)}. Open a new fish "
            "shell (or `source` those files) to pick it up."
        )


CUSTOMIZATION = FishBangBang()
