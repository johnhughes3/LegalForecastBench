import assert from "node:assert/strict";
import test from "node:test";
import { canonicalCost, hasCanonicalCosts } from "./canonical-costs.js";
import { extendSnapshot } from "./extend-snapshot.js";
import { applyReceiptCosts, receiptCosts } from "./receipt-costs.js";
import { recentResults } from "./recent-results.js";
import { historicalSnapshot, snapshot } from "./results.js";

test("native agentic exports augment and replace rows in the unchanged beta snapshot", () => {
	assert.equal(historicalSnapshot.models.length, 10);
	assert.equal(snapshot.models.length, 21);
	for (const slug of [
		"gpt-6-sol",
		"gpt-6-luna",
		"claude-opus-5-5",
		"grok-4-7",
		"gpt-4-1",
		"gemini-3-1-pro-preview",
		"gpt-6-1-sol",
		"claude-sonnet-5-5",
		"muse-wonder-1-0",
		"gemini-4-argon",
		"mistral-large-4",
	])
		assert.ok(snapshot.models.some((m) => m.slug === slug));
	for (const { source, data } of recentResults) {
		const row = data.results[0];
		assert.ok(row);
		const model = snapshot.models.find((m) => m.slug === source.slug);
		assert.equal(model?.micro_brier, data.results[0]?.micro_brier);
		assert.equal(
			model?.cost.usd ?? null,
			new Map([
				["claude-opus-5", 45.89],
				["claude-sonnet-5", 24.68],
				["gpt-5-6-sol", 24.91],
			]).get(source.slug) ??
				(hasCanonicalCosts(row.costs)
					? canonicalCost(row.costs, row.case_count).usd
					: (receiptCosts.find((cost) => cost.slug === source.slug)
							?.standard_rate_estimate_usd ?? null)),
		);
	}
});

test("Gemini and Mistral metrics use their selected complete native exports", () => {
	for (const [slug, correct, high, wrong, cost] of [
		["gemini-4-argon", 298, 225, 24, 25.0204571],
		["mistral-large-4", 294, 128, 7, 28.72776124],
	] as const) {
		const model = snapshot.models.find((row) => row.slug === slug);
		assert.ok(model, slug);
		assert.equal(model.correct, correct);
		assert.equal(model.high_confidence.count, high);
		assert.equal(model.high_confidence.wrong, wrong);
		assert.equal(model.cost.usd, cost);
	}
});

test("cost evidence must belong to the selected complete forecast and scoring run", () => {
	const costs = structuredClone(receiptCosts);
	const first = costs[0];
	assert.ok(first);
	first.forecast_run_id = "1";
	assert.throws(
		() =>
			applyReceiptCosts(
				snapshot,
				recentResults.map(({ source }) => source),
				costs,
			),
		/selected run/,
	);
});

test("missing standard-rate costs are not interpreted as zero or workload cost", () => {
	const costs = structuredClone(receiptCosts);
	for (const cost of costs) cost.standard_rate_estimate_usd = null;
	const result = applyReceiptCosts(
		extendSnapshot(historicalSnapshot, recentResults),
		recentResults.map(({ source }) => source),
		costs,
	);
	assert.ok(
		result.models
			.filter((model) => costs.some((cost) => cost.slug === model.slug))
			.every((model) => model.cost.usd === null),
	);
});
test("summary conditions cannot enter the full-document leaderboard", () => {
	const input = structuredClone(recentResults);
	const row = input[0]?.data.results[0];
	assert.ok(row);
	row.metadata.condition = "summary";
	assert.throws(
		() => extendSnapshot(historicalSnapshot, input),
		/Only agentic/,
	);
});
test("cohort changes fail even when counts agree", () => {
	const input = structuredClone(recentResults);
	const unit = input[1]?.data.results[0]?.units[0];
	assert.ok(unit);
	unit.unit_id += "-different";
	assert.throws(
		() => extendSnapshot(historicalSnapshot, input),
		/unit identities/,
	);
});
test("release mismatch fails before combining metrics", () => {
	const input = structuredClone(recentResults);
	const item = input[0];
	assert.ok(item);
	item.source.release_digest = "different";
	assert.throws(
		() => extendSnapshot(historicalSnapshot, input),
		/cohort provenance/,
	);
});

test("updated significance replaces the historical family and excludes untested models", () => {
	assert.equal(historicalSnapshot.significant_pairs.length, 3);
	assert.equal(snapshot.significant_pairs.length, 42);
	for (const pair of snapshot.significant_pairs) {
		assert.equal(pair.worse, "gpt-4-1");
		assert.notEqual(pair.better, "gpt-4-1");
	}
	assert.match(snapshot.cohort.bootstrap.correction, /210 model pairs/);
	assert.match(snapshot.cohort.bootstrap.caveat, /15 of 21/);
	assert.ok(
		!snapshot.significant_pairs.some(
			(pair) => pair.better === "grok-4-6" || pair.worse === "muse-spark-1-3",
		),
	);
});

test("the combined snapshot is dated by its newest native source", () => {
	const newest = recentResults
		.map(({ source }) => source.release_date)
		.sort()
		.at(-1);
	assert.equal(snapshot.as_of, newest);
	assert.equal(snapshot.snapshot_id, `beta-${newest}`);
	for (const model of snapshot.models) {
		assert.ok(model.release_date <= snapshot.as_of, model.slug);
	}
});
