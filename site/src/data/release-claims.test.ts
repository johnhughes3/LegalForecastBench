import assert from "node:assert/strict";
import test from "node:test";
import { comparison } from "./comparison.js";
import { assess, cutoffTable } from "./eligibility.js";
import { primarySnapshot, snapshot } from "./results.js";

test("release significance claim excludes the reference and untested models", () => {
	const tested = primarySnapshot.models.filter((model) =>
		comparison.available_models.includes(model.slug),
	);
	assert.equal(tested.length, 10);
	assert.equal(primarySnapshot.significant_pairs.length, 0);
	assert.equal(comparison.significant_pairs.length, tested.length * 3);
	assert.ok(comparison.missing_models.includes("gpt-6-astra"));
	assert.ok(comparison.missing_models.includes("gpt-5-6-luna"));
});

test("cutoff claims follow the reported-cutoff rule: fifteen eligible, two qualified", () => {
	const eligible = primarySnapshot.models.filter(
		(model) => model.eligibility === "eligible",
	);
	assert.equal(eligible.length, 15);
	assert.deepEqual(
		primarySnapshot.models
			.filter((model) => model.eligibility !== "eligible")
			.map((model) => model.slug)
			.sort(),
		["kimi-k3", "muse-spark-1-3"],
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
	// Same month as the first decision counts as preceding it.
	assert.equal(month.eligibility, "eligible");
	const july = assess(
		{ slug: "x", model_ids: [], cutoff: "2026-07", kind: "knowledge" },
		"2026-06-30",
	);
	assert.equal(july.eligibility, "qualified");
	const may = assess(
		{ slug: "x", model_ids: [], cutoff: "2026-05", kind: "knowledge" },
		"2026-06-30",
	);
	assert.equal(may.eligibility, "eligible");
});
