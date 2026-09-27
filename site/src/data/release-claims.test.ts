import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { comparison } from "./comparison.js";
import { primarySnapshot } from "./results.js";

const source = (path: string) =>
	readFileSync(new URL(path, import.meta.url), "utf8");
const report = source("../content/findings/first-release.mdx");
const home = source("../pages/index.astro");
const astra = source("../content/findings/astra-mootness.mdx");

test("release significance claim excludes the reference and untested models", () => {
	const tested = primarySnapshot.models.filter((model) =>
		comparison.available_models.includes(model.slug),
	);
	assert.equal(tested.length, 8);
	assert.equal(primarySnapshot.significant_pairs.length, 0);
	assert.equal(comparison.significant_pairs.length, tested.length * 3);
	const introduction = report.split("## Why this benchmark matters")[0] ?? "";
	assert.match(
		introduction,
		/eight current models in the paired significance analysis/,
	);
	assert.match(
		introduction,
		/The other seven current configurations were not tested pairwise/,
	);
	assert.ok(comparison.missing_models.includes("gpt-6-astra"));
	assert.ok(comparison.missing_models.includes("gpt-5-6-luna"));
	assert.doesNotMatch(astra, /simplest explanation is sampling noise/);
	assert.match(
		astra,
		/cannot establish whether Astra's observed differences reflect sampling noise/,
	);
	assert.match(
		astra,
		/Among the eight current configurations that were tested, no pairwise difference reached significance after correction; each was significantly better than the GPT-4.1 reference/,
	);
});

test("cutoff claims preserve the six eligible and nine qualified configurations", () => {
	const eligible = primarySnapshot.models.filter(
		(model) => model.eligibility === "eligible",
	);
	assert.equal(eligible.length, 6);
	assert.equal(primarySnapshot.models.length - eligible.length, 9);
	assert.match(
		report,
		/six of the fifteen configurations document a training-data cutoff/,
	);
	assert.doesNotMatch(
		report + home,
		/decisions[^.]*postdate the cutoffs providers report/i,
	);
	assert.match(
		home,
		/Six configurations have documented training-data cutoffs before every decision; the other nine are qualified/,
	);
});

test("new report captions use the readable secondary text color", () => {
	for (const component of ["ResultsTable", "HighConfidenceTable"]) {
		const table = source(`../components/${component}.astro`);
		assert.match(table, /<figcaption class="[^"]*text-ink-2/);
		assert.doesNotMatch(table, /<figcaption class="[^"]*text-ink-3/);
	}
});

test("high-confidence table scroll region is keyboard reachable and named", () => {
	const table = source("../components/HighConfidenceTable.astro");
	assert.match(
		table,
		/<div[^>]*role="region"[^>]*aria-label="High-confidence predictions"[^>]*tabindex="0"/,
	);
});
