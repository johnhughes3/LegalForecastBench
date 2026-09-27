"""Native-thin budget declaration syntax and known nonmonetary flag refusals."""

import pytest
from legalforecast.multiharness.tier0_mint import NativeThinArmInput, Tier0MintError


@pytest.mark.parametrize(
    "budget_argument",
    [
        "--model",
        "--task",
        "--run-id",
        "--max-turns",
        "--temperature",
        "--shell-timeout",
        "--reasoning-effort",
        "--skills",
        "--sandbox-image",
    ],
)
def test_native_thin_arm_refuses_known_nonmonetary_flags(
    budget_argument: str,
) -> None:
    """Correct placeholder syntax cannot turn a stock option into a dollar cap."""

    with pytest.raises(Tier0MintError, match="not a monetary budget flag"):
        NativeThinArmInput(
            executable="harvey-lab-thin",
            executable_sha256="sha256:" + "a" * 64,
            executable_version="harvey-lab-thin 1.0.0",
            version_probe_args=("--version",),
            command=("harvey-lab-thin", budget_argument, "{max_cost_usd}"),
            budget_argument=budget_argument,
        )
