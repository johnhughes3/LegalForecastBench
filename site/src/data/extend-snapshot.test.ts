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
		new Set([
			...historicalSnapshot.models.map((model) => model.slug),
			...recentResults.map(({ source }) => source.slug),
		]).size,
	);
});

test("protected historical backfills retain the saved costs for the same forecast run", () => {
	const selected = extendSnapshot(historicalSnapshot, recentResults);
	for (const slug of ["claude-opus-5", "claude-sonnet-5", "gpt-5-6-sol"]) {
		const historical = historicalSnapshot.models.find(
			(model) => model.slug === slug,
		);
		const model = selected.models.find((model) => model.slug === slug);
		assert.ok(historical && model);
		assert.equal(selected.models.filter((row) => row.slug === slug).length, 1);
		assert.ok(Math.abs(model.micro_brier - historical.micro_brier) < 1e-12);
		assert.ok(
			Math.abs(model.equal_case_brier - historical.equal_case_brier) < 1e-12,
		);
		assert.equal(model.correct, historical.correct);
		assert.equal(model.high_confidence.count, historical.high_confidence.count);
		assert.equal(model.high_confidence.wrong, historical.high_confidence.wrong);
		assert.deepEqual(model.cost, historical.cost);
	}
});

test("saved costs do not carry over to a different forecast run", () => {
	const result = structuredClone(
		recentResults.find(({ source }) => source.slug === "claude-opus-5"),
	);
	assert.ok(result);
	result.source.forecast_run = "123456789";
	const selected = extendSnapshot(historicalSnapshot, [result]);
	assert.equal(
		selected.models.find((model) => model.slug === result.source.slug)?.cost
			.usd,
		null,
	);
});

test("complete repricing replaces the saved same-run cost", () => {
	const result = structuredClone(
		recentResults.find(({ source }) => source.slug === "claude-opus-5"),
	);
	assert.ok(result);
	const row = result.data.results[0];
	assert.ok(row);
	row.costs.standard_rate_total_cost = 123;
	row.costs.standard_rate_status = "complete";
	row.costs.standard_rate_covered_case_count = row.case_count;
	const selected = extendSnapshot(historicalSnapshot, [result]);
	assert.equal(
		selected.models.find((model) => model.slug === result.source.slug)?.cost
			.usd,
		123,
	);
});
