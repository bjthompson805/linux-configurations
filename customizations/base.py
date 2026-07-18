"""Framework shared by every customization module.

A customization lives in customizations/<tier>/<name>.py and exposes a single
module-level `CUSTOMIZATION` instance of a Customization subclass. Which tier
it belongs to (recommended / opinionated / highly_opinionated) is implied by
which subpackage the file lives in -- the module itself never states its tier.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto


class Status(Enum):
    APPLICABLE = auto()       # relevant here, not yet applied -- prompt the user
    ALREADY_APPLIED = auto()  # relevant here, already in the desired state
    NOT_APPLICABLE = auto()   # doesn't apply to this system at all


@dataclass
class Detection:
    status: Status
    reason: str = ""
    # Structured detail behind `reason` (a value, a list of failing keys, ...)
    # so explain() can quote the actual finding instead of speaking generically.
    value: object = None


class Customization(ABC):
    id: str = ""
    title: str = ""

    @abstractmethod
    def detect(self) -> Detection:
        """Check current system state. Must not modify anything."""

    @abstractmethod
    def explain(self, detection: Detection) -> str:
        """Explain what applying this would do, given what detect() found.

        Only called when detection.status is APPLICABLE, so this should
        state the actual condition found (e.g. "it appears X is not set up"),
        not a generic "some systems have this problem" description.
        """

    @abstractmethod
    def apply(self) -> str:
        """Make the change. Returns a short human-readable result message."""
