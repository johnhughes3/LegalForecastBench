import assert from "node:assert/strict";
import test from "node:test";
import { extendSnapshot } from "./extend-snapshot.js";
import { recentResults } from "./recent-results.js";
import { historicalSnapshot } from "./results.js";

test("native export replaces a matching aggregate row after full cohort validation", () => {
	const result = recentResults[0];
	assert.ok(result);
	const original = extendSnapshot(historicalSnapshot, [result]);
	const replacement = structuredClone(result);
	replacement.source.forecast_run = "123456789";
	const updated = extendSnapshot(original, [replacement]);
	assert.equal(updated.models.length, original.models.length);
	assert.equal(
		updated.models.filter((m) => m.slug === result.source.slug).length,
		1,
	);
	assert.equal(
		updated.models.find((m) => m.slug === result.source.slug)?.github_run_id,
		"123456789",
	);
	assert.equal(
		original.models.find((m) => m.slug === result.source.slug)?.github_run_id,
		result.source.forecast_run,
	);
});

test("replacement requires matching slug and model key", () => {
	const result = recentResults[0];
	assert.ok(result);
	const original = extendSnapshot(historicalSnapshot, [result]);
	for (const changeSlug of [true, false]) {
		const replacement = structuredClone(result);
		if (changeSlug) replacement.source.slug += "-different";
		else {
			const row = replacement.data.results[0];
			assert.ok(row);
			row.model_id += "-different";
		}
		assert.throws(
			() => extendSnapshot(original, [replacement]),
			/Replacement model identity/,
		);
	}
});

test("duplicate replacement exports are refused", () => {
	const result = recentResults[0];
	assert.ok(result);
	const original = extendSnapshot(historicalSnapshot, [result]);
	assert.throws(
		() => extendSnapshot(original, [result, result]),
		/Duplicate native result/,
	);
});

test("a replacement with incompatible unit census cannot displace historical data", () => {
	const result = recentResults[0];
	assert.ok(result);
	const original = extendSnapshot(historicalSnapshot, recentResults);
	const replacements = structuredClone(recentResults);
	const unit = replacements[1]?.data.results[0]?.units[0];
	assert.ok(unit);
	unit.unit_id += "-different";
	assert.throws(
		() => extendSnapshot(original, replacements),
		/unit identities/,
	);
	assert.equal(
		original.models.length,
		historicalSnapshot.models.length + recentResults.length,
	);
});
