"""CLI adapter for the first-stage official corpus source package.

Two commands, one on each side of a transport: ``build`` seals a first official
staging's private corpus into a closed archive on the operator's machine, and
``open`` extracts it on the OIDC runner under the digests the dispatch pinned.

They register from their own module rather than beside the manifest-forecast
commands in ``corpus_manifest``: that adapter already sits at the reviewed size
ceiling, and these two are a self-contained flow with one implementation module
behind them. Both still land under ``acquisition``, through the same hook, so
the command surface is unchanged in shape.
"""

from __future__ import annotations

import argparse

from legalforecast.publication.manifest_run_source_package import (
    BUILD_SOURCE_PACKAGE_DESCRIPTION,
    OPEN_SOURCE_PACKAGE_DESCRIPTION,
    add_build_source_package_arguments,
    add_open_source_package_arguments,
    run_build_source_package,
    run_open_source_package,
)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the operator-side build and the runner-side open commands."""

    build = subparsers.add_parser(
        "build-manifest-run-source-package",
        help="Seal a first official manifest run's corpus into one archive.",
        description=BUILD_SOURCE_PACKAGE_DESCRIPTION,
    )
    add_build_source_package_arguments(build)
    build.set_defaults(handler=run_build_source_package)

    opener = subparsers.add_parser(
        "open-manifest-run-source-package",
        help="Extract a first-stage source package under its pinned digests.",
        description=OPEN_SOURCE_PACKAGE_DESCRIPTION,
    )
    add_open_source_package_arguments(opener)
    opener.set_defaults(handler=run_open_source_package)
