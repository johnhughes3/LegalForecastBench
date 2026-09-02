#!/bin/sh
# Seed the run's throwaway HOME with the web-retrieval fence, then become agy.
#
# The container plan bind-mounts a freshly staged HOME over the image's own, so
# a hooks.json baked into the image at $HOME would be masked and never read.
# This wrapper therefore writes it at run time, before exec'ing the CLI.  It is
# the only lever available: agy has no tool-denial flag, and its hook loader
# reads from the HOME this wrapper owns.
#
# Both documented global customization roots are seeded, and the CLI's own run
# log says what agy 1.1.22 then does with them: it migrates
# $HOME/.gemini/antigravity-cli/hooks.json to the shared
# $HOME/.gemini/config/hooks.json, symlinks the old path to the new one, and
# reports "loaded 1 named hooks from 2 hooks.json file(s)".  Either root alone
# would therefore have worked on this version.  The CLI-local copy is kept
# because agy's changelog records that path being the live one before 1.0.8,
# which makes seeding both the version-independent posture rather than a guess.
# The two files differ only in their hook name, so the migration collapses them
# to one loaded hook instead of a conflict.
#
# Nothing here touches antigravity-oauth-token: the login is copied in by
# stage_credential_home() and this wrapper only ever creates files that are
# absent, so a re-run over a populated HOME is a no-op rather than a clobber.
set -eu

if [ -z "${HOME:-}" ]; then
    echo "lfb-agy-entrypoint: HOME is unset; the container plan must set it" >&2
    exit 78
fi

seed() {
    target="$1"
    source="$2"
    mkdir -p "$(dirname "${target}")"
    if [ ! -e "${target}" ]; then
        cp "${source}" "${target}"
    fi
}

seed "${HOME}/.gemini/config/hooks.json" /opt/legalforecast/agy-hooks-shared-root.json
seed "${HOME}/.gemini/antigravity-cli/hooks.json" /opt/legalforecast/agy-hooks-cli-root.json

exec agy "$@"
