import assert from "node:assert/strict";
import test from "node:test";
import { paretoFrontier, ranks } from "./metrics.js";
import { parseSnapshot } from "./snapshot.js";
import beta from "./snapshots/beta-2026-09-18.json" with { type: "json" };

const snapshot = parseSnapshot(structuredClone(beta));

test("beta snapshot reproduces the September 18 frontiers", () => {
	const names = (metric: Parameters<typeof paretoFrontier>[1]) =>
		paretoFrontier(snapshot, metric).map((m) => m.display_name);
	assert.deepEqual(names("micro_brier"), [
		"GPT-5.6 Luna",
		"Grok 4.6",
		"Claude Fable 5.1",
	]);
	assert.deepEqual(names("equal_case_brier"), [
		"GPT-5.6 Luna",
		"Grok 4.6",
		"GPT-5.6 Sol",
	]);
	assert.deepEqual(names("accuracy"), ["GPT-5.6 Luna", "Claude Fable 5.1"]);
});

test("beta snapshot reproduces the published baselines", () => {
	const { unit_count, dismissed_unit_count, constant_forecast_micro_brier } =
		snapshot.cohort;
	const p = dismissed_unit_count / unit_count;
	assert.ok(Math.abs(p * (1 - p) - constant_forecast_micro_brier) < 1e-9);
	for (const model of snapshot.models) {
		assert.ok(model.micro_brier < constant_forecast_micro_brier, model.slug);
	}
});

test("ties share a rank", () => {
	const accuracy = ranks(snapshot, "accuracy");
	assert.equal(accuracy.get("gpt-5-6-sol"), accuracy.get("gpt-5-6-luna"));
	assert.equal(ranks(snapshot, "micro_brier").get("claude-fable-5-1"), 1);
});

test("rejects references to unknown models and impossible counts", () => {
	const bad = structuredClone(beta);
	bad.significant_pairs.push({
		better: "nope",
		worse: "grok-4-6",
		metric: "micro_brier",
	});
	assert.throws(() => parseSnapshot(bad), /unknown model/);
	const overcount = structuredClone(beta);
	const first = overcount.models[0];
	assert.ok(first);
	first.high_confidence.wrong = first.high_confidence.count + 1;
	assert.throws(() => parseSnapshot(overcount), /high-confidence misses/);
});
