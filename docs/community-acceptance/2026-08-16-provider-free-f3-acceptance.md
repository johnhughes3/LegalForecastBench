# Lane F3 provider-free community acceptance evidence

Status: provider-free acceptance complete on the candidate branch; paid Tier-0 readiness remains blocked.

Date: 2026-08-16

Baseline: `ff9fcd96`

No provider credential was resolved, no live model process was invoked, no privileged capture was attempted, and no provider spend occurred.

## Acceptance scope

The acceptance exercised the landed local-CLI registry and fake-binary machinery through the Claude and Codex clean-native Harvey LAB compositions, deterministic projection, output discovery and sealing, isolated fake evaluation, authorized-score verification, hostile native and MCP boundaries, community submission validation, aggregation, and static-site rendering.

The final focused revalidation commands were:

```bash
uv run pytest -q tests/test_multiharness_claude_clean_native_lab_e2e.py tests/test_multiharness_codex_clean_native_lab_e2e.py tests/test_harvey_lab_projection.py tests/test_harvey_lab_output_discovery.py tests/test_harvey_lab_evaluator.py tests/test_harvey_lab_authorized_scoring.py
uv run pytest -q tests/test_multiharness_hostile_native_e2e.py tests/test_multiharness_hostile_mcp_e2e.py tests/test_community_submission.py tests/test_community_publication.py tests/test_static_result_sites.py
uv run pytest -q tests/test_community_multiharness_workflow.py tests/test_package_skeleton.py tests/test_community_examples.py tests/test_community_run_summary_v2.py
```

Results:

| Phase | Result |
| --- | --- |
| Claude/Codex LAB composition, projection, discovery, isolated fake evaluation, and authorized scoring | 89 passed, 1 skipped |
| Hostile native/MCP boundaries, submission validation, aggregate, and site | 119 passed |
| Community run/package/workflow chain | 14 passed |
| Full supported four-worker suite | 8583 passed, 19 skipped |

The one skip is the explicit opt-in test requiring a caller-supplied real pinned Harvey LAB checkout. It is not a skipped provider or containment claim.

Earlier clean rebuilds in two fresh temporary roots produced byte-identical outputs after normalizing the intentionally root-dependent path field. Representative SHA-256 values were:

| Artifact | SHA-256 |
| --- | --- |
| `registry/site-summary.json` | `e70f72cb94ab7ee173d12216419da95049c192e94a91796b7be82f89c06fa1be` |
| `site/index.html` | `c1849af1b7d844a9be3541760d0c024a40d914f57bc72cc9d2444e4c408bb744` |
| normalized artifact index | `791a85d371fcde9a8ed7544254ee93a1d68ae5ab515b602a24d46878fab9483a` |

## Defect surfaced by the run

Both Harvey LAB composition functions projected the entire pinned suite and then executed the first manifest task. The existing fixture contained only the intended issue-196 task, so it concealed the possibility that a lexically earlier unrelated task would be selected.

The candidate fix passes `lab_task_ids=(ISSUE_196_LAB_TASK_ID,)` into projection and fails closed unless the result contains exactly that task. Regression fixtures add a valid lexically earlier decoy task; before the fix, both pipelines failed by looking for the decoy deliverable, and after the fix both select only `employment-labor/identify-issues-in-counterparty-motion-brief`.

This is a narrow task-selection repair. It does not activate a paid runner, change the authenticated byte contracts, weaken containment, or claim production evaluator readiness.

Three temporary mutations proved the load-bearing checks fail: removing the Claude task filter failed the decoy-task regression, removing the Codex task filter failed the corresponding regression, and changing the established pipeline task-ID assertion to the decoy ID failed against the actual issue-196 result. Each mutation was reverted before the final gates.

## Bead disposition

This evidence advances `dm0g.4.5.3`, `dm0g.4.5.4`, `dm0g.4.5.5`, and `dm0g.4.5.13`. The graph blockers remain authoritative: in particular, the privileged Claude containment capture in `dm0g.4.2.2`, the community measurement/publication checkpoint in `dm0g.4.1.15`, and the production Tier-0 operator/evaluator/budget seams prevent these beads from being represented as the completed paid acceptance chain.
