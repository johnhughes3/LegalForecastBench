#!/usr/bin/env python3
"""agy ``PreToolUse`` hook: hard-block web retrieval, and record every block.

Why this file exists rather than a CLI flag.  ``agy --help`` on 1.1.22 offers
no tool-selection, tool-denial or web-search flag, and the ``disabledTools``
key the binary carries is scoped to one MCP server entry
(``mcpServers.<name>.disabledTools``), not to the built-in tool suite -- so it
cannot close ``search_web``.  What the binary *does* carry, documented in its
own embedded hook reference, is a lifecycle-hook contract: a ``PreToolUse``
handler receives the pending tool call as JSON on stdin and may answer
``{"decision": "deny"}``, which the reference defines as "Hard block the
execution immediately."  That is a local, deterministic gate on a named tool,
which is exactly the fence this lane needs.

Why the fence has to exist at all.  ``search_web`` is *dispatched* by the CLI
but *executed upstream* -- the binary carries an
``ApiServerService/GetWebSearchResults`` method and a
``generateContentResponseToWebSearchResults`` converter -- so the search runs
on the vendor's infrastructure, inside the same TLS session the run needs for
the model itself.  No container egress rule reaches it.  The forecast targets
are real federal cases whose outcomes are one search away, so a tools-on agy
row is only publishable if that tool never fires.

The handler is deliberately incapable of failing open.  Every step that could
raise -- reading stdin, decoding it, appending the record -- is contained, and
the deny decision is printed unconditionally on the way out.  A hook that
crashed would hand agy no decision at all, and this file must never be the
reason a web call was allowed.
"""

from __future__ import annotations

import json
import sys
from typing import Any

# The run's own record that the fence engaged, written where it survives the
# container: /workspace is the bind-mounted run workspace, while HOME and the
# rootfs are torn down with the container.  Appending is best-effort -- a run
# that cannot journal the block is still a run in which the block happened.
DENIAL_LOG = "/workspace/.lfb-agy-tool-denials.jsonl"
REASON = (
    "Web retrieval is disabled for this benchmark run. Answer from the record "
    "in your working directory. Do not retry this tool or look for another "
    "route to the web."
)


def tool_name(payload: object) -> str:
    """Return the pending tool's name, or ``unknown`` for any other shape."""

    if not isinstance(payload, dict):
        return "unknown"
    call: Any = payload.get("toolCall")
    if not isinstance(call, dict):
        return "unknown"
    name: Any = call.get("name")
    return name if isinstance(name, str) and name else "unknown"


def record_denial(name: str) -> None:
    """Append one denial record to the run's journal."""

    line = json.dumps(
        {"denied_tool": name, "fence": "lfb_agy_web_retrieval"}, sort_keys=True
    )
    with open(DENIAL_LOG, "a", encoding="utf-8") as handle:
        handle.write(f"{line}\n")


def main() -> int:
    """Deny the pending tool call, journalling it if the journal is writable."""

    name = "unknown"
    try:
        name = tool_name(json.loads(sys.stdin.read() or "{}"))
    except (OSError, ValueError):
        pass
    try:
        record_denial(name)
    except OSError:
        pass
    print(json.dumps({"decision": "deny", "reason": REASON}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
