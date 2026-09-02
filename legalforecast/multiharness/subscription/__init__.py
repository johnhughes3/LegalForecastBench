"""Contributor-subscription presence proving for local harness CLIs."""

from legalforecast.multiharness.subscription.local_login import (
    HARNESS_LOGIN_DESCRIPTORS,
    HarnessLoginDescriptor,
    LocalLoginPresence,
    descriptor_for_executable,
    local_login_presence_for,
)

__all__ = [
    "HARNESS_LOGIN_DESCRIPTORS",
    "HarnessLoginDescriptor",
    "LocalLoginPresence",
    "descriptor_for_executable",
    "local_login_presence_for",
]
