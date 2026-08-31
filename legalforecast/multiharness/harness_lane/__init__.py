"""The containerized, tools-on agentic CLI harness lane.

This lane answers a question the main benchmark cannot: does an agentic CLI
harness beat the bare provider API on the same motion-to-dismiss forecast?
Each harness therefore runs with its own local tool suite live, inside a
digest-pinned container whose egress is confined to the provider's endpoints,
and with provider-executed web retrieval declared off -- no container rule can
stop a server-side ``web_search``, and the forecast targets are real federal
cases.  Results stay in their own lane and never merge into official numbers.

:mod:`.harnesses` names the five harnesses, :mod:`.auth` bridges a
contributor's own login into the container, :mod:`.adapter` is the
manifest-driven ``HarnessAdapter``, :mod:`.preflight` is the no-spend
readiness probe, and :mod:`.cli_parser` exposes it under
``legalforecast multiharness harness``.

Nothing is re-exported here on purpose.  ``adapter_registry`` reaches
:mod:`.harnesses` for the family's names during registration, and a package
``__init__`` that pulled in :mod:`.adapter` would drag the container runtime
and the manifest model into every ``multiharness adapters list``.
"""
