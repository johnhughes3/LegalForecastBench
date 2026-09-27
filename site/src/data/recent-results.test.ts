import assert from "node:assert/strict";
import test from "node:test";
import { extendSnapshot } from "./extend-snapshot.js";
import { recentResults } from "./recent-results.js";
import { historicalSnapshot, snapshot } from "./results.js";

test("all six newer agentic models augment the unchanged beta snapshot", () => {
	assert.equal(historicalSnapshot.models.length, 10);
	assert.equal(snapshot.models.length, 16);
	for (const slug of [
		"gpt-6-sol",
		"gpt-6-luna",
		"claude-opus-5-5",
		"grok-4-7",
		"gpt-4-1",
		"gemini-3-1-pro-preview",
	])
		assert.ok(snapshot.models.some((m) => m.slug === slug));
	for (const { source, data } of recentResults) {
		const model = snapshot.models.find((m) => m.slug === source.slug);
		assert.equal(model?.micro_brier, data.results[0]?.micro_brier);
		assert.equal(model?.cost.usd, data.results[0]?.costs.total_cost);
	}
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
	assert.equal(snapshot.significant_pairs.length, 24);
	for (const pair of snapshot.significant_pairs) {
		assert.equal(pair.worse, "gpt-4-1");
		assert.notEqual(pair.better, "gpt-4-1");
	}
	assert.match(snapshot.cohort.bootstrap.correction, /120 model pairs/);
	assert.match(snapshot.cohort.bootstrap.caveat, /9 of 16/);
	assert.ok(
		!snapshot.significant_pairs.some(
			(pair) => pair.better === "grok-4-6" || pair.worse === "muse-spark-1-3",
		),
	);
});
