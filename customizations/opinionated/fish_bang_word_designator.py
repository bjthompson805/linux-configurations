import shutil

from customizations import util
from customizations.base import Customization, Detection, Status

FUNCTIONS_DIR = util.FISH_DIR / "functions"
CONF_D_DIR = util.FISH_DIR / "conf.d"

HISTORY_PREVIOUS_COMMAND_WORD = FUNCTIONS_DIR / "__history_previous_command_word.fish"
KEY_BINDINGS = CONF_D_DIR / "plugin-bang-bang-word-designator.fish"

HISTORY_PREVIOUS_COMMAND_WORD_CONTENT = """function __history_previous_command_word
    # Bash-style !:N word designator (N=0 is the command, N=1.. are args).
    # Only fires when the token so far is exactly "!:" (from "!" + ":");
    # any other token means the digit was typed normally.
    set -l n $argv[1]
    switch (commandline -t)
    case "!:"
        if test (count $history) -eq 0
            commandline -i $n
            commandline -f repaint
            return
        end
        set -l words (string split ' ' -- $history[1] | string match -vr '^$')
        set -l idx (math $n + 1)
        if test $idx -le (count $words)
            commandline -t $words[$idx]
        else
            commandline -t ""
        end
        commandline -f repaint
    case "*"
        commandline -i $n
    end
end
"""

KEY_BINDINGS_CONTENT = """# Extends plugin-bang-bang (which only wires up "!" and "$") with bash-style
# word designators: !:0, !:1, !:2, ... !:9.
# Kept as a separate file so re-running the fish-bang-bang customization (or
# a fisher install of plugin-bang-bang) won't clobber this.

function _bang_word_designator_key_bindings --on-variable fish_key_bindings
    for d in 0 1 2 3 4 5 6 7 8 9
        bind --erase $d 2>/dev/null
    end
    switch "$fish_key_bindings"
    case 'fish_default_key_bindings'
        for d in 0 1 2 3 4 5 6 7 8 9
            bind --mode default $d "__history_previous_command_word $d"
        end
    case 'fish_vi_key_bindings' 'fish_hybrid_key_bindings'
        for d in 0 1 2 3 4 5 6 7 8 9
            bind --mode insert $d "__history_previous_command_word $d"
        end
    end
end

function _bang_word_designator_uninstall --on-event plugin-bang-bang-word-designator_uninstall
    for d in 0 1 2 3 4 5 6 7 8 9
        bind --erase $d
    end
    functions --erase _bang_word_designator_uninstall
end

_bang_word_designator_key_bindings
"""

FILES = {
    HISTORY_PREVIOUS_COMMAND_WORD: HISTORY_PREVIOUS_COMMAND_WORD_CONTENT,
    KEY_BINDINGS: KEY_BINDINGS_CONTENT,
}


class FishBangWordDesignator(Customization):
    id = "fish-bang-word-designator"
    title = "Add bash-style !:N word designators to fish"

    def explain(self, detection: Detection) -> str:
        missing = detection.value
        return (
            "It appears fish doesn't expand bash-style history word "
            "designators -- typing `!:1`, `!:2`, etc. inserts them "
            "literally instead of substituting the Nth word of the "
            "previous command, since fish has no built-in equivalent and "
            "the plugin-bang-bang plugin (see the fish-bang-bang "
            "customization) only covers `!!` and `!$`. This adds a small "
            f"companion file rather than modifying that plugin: "
            f"{', '.join(str(p) for p in missing)}.\n\n"
            "It binds digit keys 0-9 in whichever key-binding mode you're "
            "using (default or vi-insert) so that typing `!:` followed by "
            "a digit N expands in place to word N of the previous command "
            "-- N=0 is the command name itself, N=1.. are its arguments, "
            "matching bash. Any other digit typed normally still just "
            "types normally."
        )

    def detect(self) -> Detection:
        if shutil.which("fish") is None:
            return Detection(Status.NOT_APPLICABLE, "fish is not installed")
        if not util.FISH_DIR.is_dir():
            return Detection(Status.NOT_APPLICABLE, "no ~/.config/fish directory found")

        missing = [path for path, content in FILES.items() if not (path.exists() and path.read_text() == content)]
        if not missing:
            return Detection(Status.ALREADY_APPLIED, "the word-designator key bindings are already installed")
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


CUSTOMIZATION = FishBangWordDesignator()
