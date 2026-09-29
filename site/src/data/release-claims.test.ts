import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { comparison } from "./comparison.js";
import { assess, cutoffTable } from "./eligibility.js";
import { primarySnapshot, snapshot } from "./results.js";

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

test("cutoff claims follow the reported-cutoff rule: eleven eligible, four qualified", () => {
	const eligible = primarySnapshot.models.filter(
		(model) => model.eligibility === "eligible",
	);
	assert.equal(eligible.length, 11);
	assert.deepEqual(
		primarySnapshot.models
			.filter((model) => model.eligibility !== "eligible")
			.map((model) => model.slug)
			.sort(),
		["claude-fable-5-1", "claude-opus-5-5", "kimi-k3", "muse-spark-1-3"],
	);
	assert.match(
		report,
		/eleven of the fifteen configurations report a training-data or knowledge cutoff before the first decision/,
	);
	assert.doesNotMatch(
		report + home,
		/decisions[^.]*postdate the cutoffs providers report/i,
	);
	// The home page computes its counts from the data rather than hard-coding them.
	assert.match(
		home,
		/\$\{eligibleCount\} of \$\{primarySnapshot\.models\.length\} configurations report a training or knowledge cutoff/,
	);
});

test("eligibility comes from the shared cutoff table for every displayed model", () => {
	for (const model of snapshot.models) {
		const entry = cutoffTable.find((e) => e.slug === model.slug);
		assert.ok(entry, model.slug);
		assert.equal(
			assess(entry, snapshot.cohort.decision_window.start).eligibility,
			model.eligibility,
		);
	}
	const month = assess(
		{ slug: "x", model_ids: [], cutoff: "2026-06", kind: "knowledge" },
		"2026-06-30",
	);
	assert.equal(month.eligibility, "qualified");
	const may = assess(
		{ slug: "x", model_ids: [], cutoff: "2026-05", kind: "knowledge" },
		"2026-06-30",
	);
	assert.equal(may.eligibility, "eligible");
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
