# linux-configurations

A terminal UI that walks through Hyprland/Arch Linux customizations one
screen at a time, so you can see exactly what the tool found and decide
whether to apply it.

## Usage

```
./customize.py
```

Requires Python 3.10+ and a terminal (curses), nothing else.

Customizations are grouped into three tiers, presented in order:

1. **Recommended** -- bug fixes and changes almost anyone would want.
2. **Opinionated** -- changes the author likes, others might not.
3. **Highly opinionated** -- changes specific to the author's own setup.

Each tier starts with its own transition screen naming the tier and what it
means before showing its customizations. Every customization gets a full
screen -- including ones that don't apply to your system or are already
applied -- so it's always clear what the tool checked and decided, not just
the ones it's asking you to act on.

### Controls

| Key(s)          | Action                                    |
|-----------------|--------------------------------------------|
| `→` / `l` / `n` | Next screen                                |
| `←` / `h` / `p` | Previous screen                            |
| `↓`/`↑` or `j`/`k` | Scroll long text on the current screen  |
| `a` / `Enter`   | Apply the customization being shown        |
| `q`             | Quit                                       |

You can move back and forth freely at any time -- there's no gate before
highly-opinionated customizations, and nothing is applied without pressing
`a` on that customization's own screen. Press `q` whenever you're done,
whether that's partway through or after reaching the end; a report of what
was applied, already applied, skipped, or not applicable is printed to the
terminal, and is also its own screen you can page back to before quitting.

For every customization the tool first checks whether it's even relevant to
your system (e.g. skips laptop-backlight binds if you have no backlight, or
Ryoku-specific tweaks if Ryoku isn't installed) and whether it's already
applied -- that result is what each screen shows. Any file a customization
edits in place is backed up first, next to the original with a
`.bak.<timestamp>` suffix.

## Advanced
### Adding a new customization

Drop a new `.py` file into `customizations/recommended/`,
`customizations/opinionated/`, or `customizations/highly_opinionated/`
depending on which tier it belongs to -- the directory it lives in *is* its
tier, nothing else declares it. The file must define a module-level
`CUSTOMIZATION` instance of a `Customization` subclass
(see `customizations/base.py`):

```python
from customizations.base import Customization, Detection, Status

class MyThing(Customization):
    id = "my-thing"
    title = "One-line description shown while scanning"

    def detect(self) -> Detection:
        # Read-only. Return NOT_APPLICABLE if it doesn't apply to this
        # system, ALREADY_APPLIED if it's already in the desired state, or
        # APPLICABLE if it should be offered -- pass along whatever you
        # found via `reason`/`value` so explain() can state it concretely.
        ...

    def explain(self, detection: Detection) -> str:
        # Only called when detection.status is APPLICABLE. State the actual
        # condition found (detection.value/reason), e.g. "it appears X is
        # not set up" -- not a generic "some systems have this problem".
        ...

    def apply(self) -> str:
        # Make the change, return a short human-readable result message.
        ...

CUSTOMIZATION = MyThing()
```

It's picked up automatically -- nothing else needs to be registered or
imported by hand. `customizations/util.py` has shared helpers for editing
Hyprland's Lua config and backing up files before an in-place edit.
