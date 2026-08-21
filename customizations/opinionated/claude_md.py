import shutil
from pathlib import Path

from customizations import util
from customizations.base import Customization, Detection, Status

CLAUDE_DIR = Path.home() / ".claude"
CLAUDE_MD = CLAUDE_DIR / "CLAUDE.md"

CONTENT = """# Critical Instructions for Claude

## Thinking Process & Scope
- NEVER rely on a shallow file search or make quick assumptions about my system configuration.
- Before writing code or proposing a solution, you MUST "think deeply": trace configuration dependencies across files, look at my actual config files, and verify what software is actively installed or running.
- If a detail is missing, do not guess. Run a terminal command to check, or stop and ask me.

## Quality & Verification
- Sanity-check all JSONC and CSS syntax before completing a task.
- Treat every modification as a complex system interaction, not a simple copy-paste job.

## Reverting Failed Changes
If the user reports that a change simply "did not work" or had no effect, immediately revert it before proposing or applying any alternative. Do not leave failed changes in place while iterating.

## Slow and careful thoughts
Make sure to slowly and carefully respond to the user, checking your work before saying anything.

## Patching-system projects: test before releasing a patch
This applies to ANY project that keeps its source pristine at upstream and maintains local features as `patches/*.patch` (e.g. nwg-drawer).
- NEVER copy/move a new or changed patch into the main project directory (the "release" step) until I have built the binary and personally tested it. Producing/exporting the patch in a scratch or throwaway worktree is fine; landing it in the project's `patches/` is the gated step.
- After building, STOP and explicitly prompt me to run and test the resulting binary. Wait for my confirmation that it works before copying the patch into the main directory or committing it.
- If I report the behavior is wrong, fix it and repeat the build-and-test cycle before any release.

## Downloading
Do not download without first checking with me, as I am always on a tethered connection to my phone, and the data cap is very low.

## Long-running commands
If a command will take an exceedingly long time to run, ask me first whether I'd rather run it myself in my own terminal, instead of just running it and waiting on it.

"""


class ClaudeMd(Customization):
    id = "claude-md-instructions"
    title = "Install a pre-written CLAUDE.md with stricter verification/workflow rules"

    def explain(self, detection: Detection) -> str:
        return (
            "It appears no ~/.claude/CLAUDE.md exists yet. This installs a "
            "pre-written CLAUDE.md of personal working-agreement rules for "
            "Claude Code: don't guess at system config, verify by reading "
            "actual files/running commands, sanity-check JSONC/CSS before "
            "finishing, revert a failed change before trying an "
            "alternative, go slowly and check work before responding, gate "
            "patch-system releases on a personally-tested build, and never "
            "download without asking first (tethered/metered "
            "connection), and offer to let me run exceedingly "
            "long-running commands myself instead of just running "
            "them.\n\n"
            f"{util.indent(CONTENT.rstrip())}"
        )

    def detect(self) -> Detection:
        if shutil.which("claude") is None and not CLAUDE_DIR.exists():
            return Detection(Status.NOT_APPLICABLE, "Claude Code doesn't appear to be installed (no `claude` on PATH and no ~/.claude directory)")
        if not CLAUDE_MD.exists():
            return Detection(Status.APPLICABLE, "no ~/.claude/CLAUDE.md found")
        current = CLAUDE_MD.read_text()
        if current == CONTENT:
            return Detection(Status.ALREADY_APPLIED, "~/.claude/CLAUDE.md already matches")
        return Detection(
            Status.NOT_APPLICABLE,
            "~/.claude/CLAUDE.md already exists with different content -- leaving the user's existing file alone",
        )

    def apply(self) -> str:
        CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
        CLAUDE_MD.write_text(CONTENT)
        return f"Wrote {CLAUDE_MD}."


CUSTOMIZATION = ClaudeMd()
