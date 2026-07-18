# linux-configurations

An interactive tool that walks through Hyprland/Arch Linux customizations and
lets you decide, one at a time, which ones to apply. Each customization
explains what it does and how it works before asking.

## Usage

```
./customize.py
```

Requires Python 3.10+, nothing else.

Customizations are grouped into three tiers, applied in order:

1. **Recommended** -- bug fixes and changes almost anyone would want. Always
   reviewed.
2. **Opinionated** -- changes the author likes, others might not. Always
   reviewed.
3. **Highly opinionated** -- changes specific to the author's own setup.
   Reviewed only if you opt in when prompted.

For every customization the tool first checks whether it's even relevant to
your system (e.g. skips laptop-backlight binds if you have no backlight, or
Ryoku-specific tweaks if Ryoku isn't installed) and whether it's already
applied. You're only prompted for ones that are relevant and not yet applied.
Any file a customization edits in place is backed up first, next to the
original with a `.bak.<timestamp>` suffix.

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
