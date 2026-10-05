/**
 * Refresh the vendored Harvey LAB task files used by the LAB explorer.
 *
 * The explorer builds offline, so each pinned `task.json` (instructions and the
 * full rubric) is committed under `src/data/lab/upstream/`. Run this only when
 * the audited Harvey revision changes: `pnpm exec tsx scripts/fetch-lab-upstream.ts`.
 * Files are written byte-for-byte as served so a diff against upstream stays
 * meaningful. Upstream is MIT licensed; the notice is committed alongside.
 */
import { mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { HARVEY_COMMIT, rawTaskUrl } from "../src/lab/upstream.js";

const here = dirname(fileURLToPath(import.meta.url));
const auditTasks = resolve(
	here,
	"../../docs/harvey-lab-audit/litigation-dispute-resolution/tasks",
);
const out = resolve(here, "../src/data/lab/upstream");
mkdirSync(out, { recursive: true });

const tasks = readdirSync(auditTasks, { withFileTypes: true })
	.filter((entry) => entry.isDirectory())
	.map((entry) => entry.name)
	.sort();

for (const task of tasks) {
	const response = await fetch(rawTaskUrl(task));
	if (!response.ok)
		throw new Error(`${task}: HTTP ${response.status} at ${HARVEY_COMMIT}`);
	writeFileSync(resolve(out, `${task}.json`), await response.text());
}
console.log(`Wrote ${tasks.length} task files for ${HARVEY_COMMIT}.`);
