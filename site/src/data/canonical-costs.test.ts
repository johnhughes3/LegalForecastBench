import assert from "node:assert/strict";
import test from "node:test";
import type { SiteCosts } from "../generated/site-export.js";
import { canonicalCost } from "./canonical-costs.js";
import { extendSnapshot } from "./extend-snapshot.js";
import { applyReceiptCosts, receiptCosts } from "./receipt-costs.js";
import { recentResults } from "./recent-results.js";
import { historicalSnapshot } from "./results.js";

const costs: SiteCosts = {
	basis: "provider_reported",
	total_cost: 1.5,
	cost_per_case: 0.75,
	covered_case_count: 2,
	missing_case_count: 0,
	standard_rate_total_cost: 2,
	standard_rate_status: "complete",
	standard_rate_covered_case_count: 2,
	missing_cache_read_response_count: 1,
	missing_cache_write_response_count: 2,
	missing_cache_rate_response_count: 3,
	missing_response_usage_case_count: 0,
	caveats: [
		"Excludes failed attempts and unresolved charges; not invoice totals.",
	],
};

test("canonical charts use standard repricing while displaying the actual charge separately", () => {
	const result = canonicalCost(costs, 2);
	assert.equal(result.usd, 2);
	assert.equal(result.basis, "standard_rate");
	assert.match(result.note ?? "", /reported charge: \$1.5000/);
	assert.match(result.note ?? "", /missing cache prices: 3/);
	assert.match(result.note ?? "", /not invoice totals/);
	assert.match(
		canonicalCost({ ...costs, basis: "estimated_from_pricing_snapshot" }, 2)
			.note ?? "",
		/usage estimate/,
	);
});

test("partial or absent repricing keeps chart cost null and reports workload coverage", () => {
	for (const row of [
		{
			...costs,
			standard_rate_status: "partial" as const,
			standard_rate_covered_case_count: 1,
		},
		{ ...costs, standard_rate_total_cost: null },
		{ ...costs, covered_case_count: 1, missing_case_count: 1 },
	]) {
		const result = canonicalCost(row, 2);
		assert.equal(result.usd, null);
		assert.equal(result.basis, "unavailable");
		assert.match(result.note ?? "", /Excluded from comparative cost charts/);
		assert.match(result.note ?? "", /Successful workload reported charge/);
	}
});

test("canonical scoring evidence overrides legacy saved costs including missing repricing", () => {
	const additions = structuredClone(recentResults);
	const first = additions[0];
	assert.ok(first);
	const row = first.data.results[0];
	assert.ok(row);
	row.costs = {
		...costs,
		covered_case_count: row.case_count,
		standard_rate_covered_case_count: row.case_count,
		standard_rate_total_cost: 123,
	};
	const saved = structuredClone(receiptCosts);
	const fallback = saved.find((cost) => cost.slug === first.source.slug);
	assert.ok(fallback);
	fallback.forecast_run_id = "stale";
	let result = applyReceiptCosts(
		extendSnapshot(historicalSnapshot, additions),
		additions.map(({ source }) => source),
		saved,
		additions,
	);
	assert.equal(
		result.models.find((model) => model.slug === first.source.slug)?.cost.usd,
		123,
	);
	row.costs.standard_rate_total_cost = null;
	row.costs.standard_rate_status = "unavailable";
	result = applyReceiptCosts(
		extendSnapshot(historicalSnapshot, additions),
		additions.map(({ source }) => source),
		saved,
		additions,
	);
	assert.equal(
		result.models.find((model) => model.slug === first.source.slug)?.cost.usd,
		null,
	);
});
