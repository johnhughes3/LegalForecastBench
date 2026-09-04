#!/usr/bin/env python3
"""Unbypassable web/search fence for tools-on agentic CLIs.

Standard library only, and no imports from the rest of ``legalforecast``: the
same file is unit-tested on the host, staged as a 0755 binary, and bind-mounted
into the harness container as every name the agent might type (``claude``,
``codex``, ``grok``, ``agy``, and ``lfb-cli-fence``).  Nested invocation is the
reason it exists.  Disable flags on the *initial* ``docker run`` argv are not a
fence, because the evaluated agent has a shell plus the same executable plus
credentials and can re-invoke without those flags.

The wrapper always injects the vendor's web/search disable flags, strips the
flags that would turn those tools back on, and execs the real binary from the
image-baked libexec path.  It does not consult HOME, settings.json, environment
overrides, or any other agent-writable config for tool enablement.  Image build
should place the vendor binary at ``/opt/legalforecast/libexec/<cli>`` via
:func:`install_cli_fence` so the only ``PATH`` hit for that name is this
wrapper.

What this file cannot do: stop a provider-side web tool that ignores the
vendor's own disable flag.  That is a parser-observation problem, not a PATH
problem.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

WRAPPER_NAME: Final[str] = "lfb-cli-fence"
FENCED_CLIS: Final[frozenset[str]] = frozenset({"agy", "claude", "codex", "grok"})
DEFAULT_LIBEXEC_DIR: Final[str] = "/opt/legalforecast/libexec"
DEFAULT_BIN_DIR: Final[str] = "/opt/legalforecast/bin"
DEFAULT_CREDENTIALS_ROOT: Final[str] = "/run/legalforecast/credentials"

CLAUDE_DISABLE_FLAG: Final[str] = "--disallowedTools"
CLAUDE_DISABLE_TOOLS: Final[tuple[str, ...]] = ("WebSearch", "WebFetch")
CLAUDE_TOOL_FLAGS: Final[frozenset[str]] = frozenset(
    {
        "--allowedTools",
        "--allowed-tools",
        "--disallowedTools",
        "--disallowed-tools",
    }
)
CODEX_WEB_SEARCH_CONFIG: Final[str] = 'web_search="disabled"'
GROK_DISABLE_FLAG: Final[str] = "--disable-web-search"
GROK_ENABLE_FLAGS: Final[frozenset[str]] = frozenset(
    {"--disable-web-search", "--enable-web-search"}
)

_AGY_DENY_SCRIPT: Final[str] = (
    "#!/usr/bin/env python3\n"
    "import json, sys\n"
    "try:\n"
    "    json.loads(sys.stdin.read() or '{}')\n"
    "except ValueError:\n"
    "    pass\n"
    "print(json.dumps({'decision': 'deny',"
    " 'reason': 'web retrieval disabled'}))\n"
)
_AGY_HOOK_MATCHER: Final[str] = "^(search_web|read_url_content|[a-z_]*browser[a-z_]*)$"


class CliFenceError(RuntimeError):
    """Raised when the fence cannot be applied or installed."""


def fenced_argv(cli: str, user_argv: Sequence[str]) -> list[str]:
    """Return argv (no program name) with web/search forced off.

    ``user_argv`` is whatever the agent typed after the CLI name, including a
    nested invocation that omitted the disable flags or that tried to turn
    the tools back on.  HOME-sourced config is not consulted.
    """

    if cli not in FENCED_CLIS:
        raise CliFenceError(f"not a fenced tools-on CLI: {cli!r}")
    args = [str(item) for item in user_argv]
    if cli == "claude":
        stripped = _strip_flag_and_values(args, CLAUDE_TOOL_FLAGS)
        return [CLAUDE_DISABLE_FLAG, *CLAUDE_DISABLE_TOOLS, *stripped]
    if cli == "codex":
        subcommand, rest = _split_subcommand(args)
        stripped = _strip_codex_web_config(
            _strip_flag_and_values(rest, GROK_ENABLE_FLAGS)
        )
        fenced = ["-c", CODEX_WEB_SEARCH_CONFIG, "--ignore-user-config", *stripped]
        return [subcommand, *fenced] if subcommand is not None else fenced
    if cli == "grok":
        stripped = _strip_flag_and_values(args, GROK_ENABLE_FLAGS)
        return [GROK_DISABLE_FLAG, *stripped]
    return list(args)


def install_cli_fence(
    *,
    bin_dir: Path,
    libexec_dir: Path,
    cli: str,
    real_binary: Path,
) -> Path:
    """Install this wrapper as ``cli`` and copy the vendor binary to libexec.

    Image builds call this so ``PATH`` lookup and a naive absolute path under
    the bin dir both hit the wrapper.  The vendor binary is *copied* to
    libexec; the caller removes the original PATH entry.
    """

    if cli not in FENCED_CLIS:
        raise CliFenceError(f"not a fenced tools-on CLI: {cli!r}")
    if not real_binary.is_file() or real_binary.is_symlink():
        raise CliFenceError(f"real CLI binary must be a regular file: {cli}")
    libexec_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    dest_real = libexec_dir / cli
    if dest_real.resolve() != real_binary.resolve():
        dest_real.write_bytes(real_binary.read_bytes())
        dest_real.chmod(0o755)
    wrapper = Path(__file__).read_bytes()
    installed = bin_dir / cli
    for name in (cli, WRAPPER_NAME):
        path = bin_dir / name
        path.write_bytes(wrapper)
        path.chmod(0o755)
    return installed


def materialize_runtime_home(home: Path, credentials_root: Path | None) -> None:
    """Copy missing credential files into the writable HOME, never clobbering.

    The credential mount is read-only so the evaluated agent cannot rewrite
    the operator-staged secrets.  OAuth refresh writes into HOME; a second
    nested invocation must not replace those refreshed tokens.  Symlinks in
    either tree are skipped.
    """

    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    if credentials_root is None or not credentials_root.is_dir():
        return
    for source in credentials_root.rglob("*"):
        if source.is_symlink() or not source.is_file():
            continue
        relative = source.relative_to(credentials_root)
        destination = home.joinpath(*relative.parts)
        if destination.exists() or destination.is_symlink():
            continue
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        destination.chmod(0o600)


def seed_agy_web_fence(home: Path) -> None:
    """Always rewrite agy's hook files so a nested invocation is still fenced.

    agy has no tool-denial flag.  The halted stack seeded hooks only when the
    files were absent, which let the agent rewrite them and re-invoke.  This
    always overwrites the fence-owned files.
    """

    deny = home / ".lfb-fence" / "deny-web-tools"
    deny.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    deny.write_text(_AGY_DENY_SCRIPT, encoding="utf-8")
    deny.chmod(0o755)
    hooks = {
        "lfb-web-fence": {
            "enabled": True,
            "PreToolUse": [
                {
                    "matcher": _AGY_HOOK_MATCHER,
                    "hooks": [
                        {
                            "type": "command",
                            "command": str(deny),
                            "timeout": 10,
                        }
                    ],
                }
            ],
        }
    }
    payload = json.dumps(hooks)
    for relative in (
        ".gemini/config/hooks.json",
        ".gemini/antigravity-cli/hooks.json",
    ):
        path = home / relative
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")


def resolve_cli(argv0: str, args: Sequence[str]) -> tuple[str, list[str]]:
    """Return ``(cli, user_argv)`` from a wrapper invocation."""

    programmed = Path(argv0).name
    remaining = [str(item) for item in args]
    if programmed in FENCED_CLIS:
        return programmed, remaining
    if remaining and remaining[0] in FENCED_CLIS:
        return remaining[0], remaining[1:]
    env_cli = os.environ.get("LFB_HARNESS_CLI", "")
    if env_cli in FENCED_CLIS:
        return env_cli, remaining
    raise CliFenceError(
        "cannot determine which fenced CLI to exec; set LFB_HARNESS_CLI"
    )


def resolve_real_binary(cli: str) -> Path:
    """Return the vendor binary from the baked libexec path, never from env.

    ``LFB_HARNESS_REAL_BIN`` is ignored even if present: the evaluated agent
    has a shell and would otherwise point this wrapper at an unfenced copy.
    """

    here = Path(__file__).resolve().parent
    candidates = (
        here.parent / "libexec" / cli,
        Path(DEFAULT_LIBEXEC_DIR) / cli,
    )
    wrapper = Path(__file__).resolve()
    for candidate in candidates:
        if not candidate.is_file() or candidate.is_symlink():
            continue
        resolved = candidate.resolve()
        if resolved == wrapper:
            continue
        return resolved
    raise CliFenceError(f"real {cli} binary is not installed")


def main(argv: Sequence[str] | None = None) -> int:
    """Fence the invocation and exec the vendor CLI.  Never returns on success."""

    args = list(sys.argv[1:] if argv is None else argv)
    argv0 = sys.argv[0] if argv is None else WRAPPER_NAME
    try:
        cli, user_argv = resolve_cli(argv0, args)
        home = Path(os.environ.get("HOME") or "/home/harness")
        credentials = os.environ.get("LFB_CREDENTIALS_ROOT")
        materialize_runtime_home(home, Path(credentials) if credentials else None)
        if cli == "agy":
            seed_agy_web_fence(home)
        real = resolve_real_binary(cli)
        fenced = fenced_argv(cli, user_argv)
    except CliFenceError as exc:
        print(f"lfb-cli-fence: {exc}", file=sys.stderr)
        return 78
    os.environ.pop("LFB_HARNESS_REAL_BIN", None)
    os.execv(str(real), [cli, *fenced])
    return 78


def _split_subcommand(args: list[str]) -> tuple[str | None, list[str]]:
    if args and not args[0].startswith("-"):
        return args[0], args[1:]
    return None, args


def _strip_flag_and_values(args: list[str], flags: frozenset[str]) -> list[str]:
    out: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        name = token.split("=", 1)[0]
        if name in flags:
            if "=" in token:
                index += 1
                continue
            index += 1
            while index < len(args) and not args[index].startswith("-"):
                index += 1
            continue
        out.append(token)
        index += 1
    return out


def _strip_codex_web_config(args: list[str]) -> list[str]:
    out: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token in {"-c", "--config"} and index + 1 < len(args):
            key = args[index + 1].split("=", 1)[0].strip().strip('"')
            if "web_search" in key:
                index += 2
                continue
        if token in {"--enable", "--disable"} and index + 1 < len(args):
            if "web_search" in args[index + 1]:
                index += 2
                continue
        out.append(token)
        index += 1
    return out


if __name__ == "__main__":
    raise SystemExit(main())
