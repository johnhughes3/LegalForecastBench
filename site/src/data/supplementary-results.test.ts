import assert from "node:assert/strict";
import test from "node:test";
import gpt41 from "./exports/gpt-4-1.json";
import { snapshot } from "./results";
import { parseSiteExport } from "./site-export";
import {
	buildSupplementaryRows,
	summaryComparisons,
	supplementaryRows,
} from "./supplementary-results";

test("summary results remain separate and use the same 91-case, 387-unit cohort", () => {
	assert.equal(supplementaryRows.length, 5);
	assert.equal(summaryComparisons.length, 4);
	for (const row of supplementaryRows) {
		assert.equal(row.case_count, 91);
		assert.equal(row.unit_count, 387);
	}
	assert.equal(
		supplementaryRows.find((row) => row.slug === "gpt-6-luna-summaries-none")
			?.correct,
		287,
	);
	assert.equal(
		supplementaryRows.find((row) => row.slug === "jev-luna-summaries")?.correct,
		126,
	);
	assert.equal(
		supplementaryRows.find((row) => row.role === "reasoning-reference")
			?.display_name,
		"GPT-5.6 Luna",
	);
	assert.equal(
		supplementaryRows.find((row) => row.slug === "gpt-4-1")?.role,
		"full-record-reference",
	);
	assert.equal(snapshot.models.length, 18);
	assert.ok(
		summaryComparisons.every(
			({ source }) =>
				!snapshot.models.some((model) => model.slug === source.slug),
		),
	);
});

test("summary comparison rejects different outcomes, conditions, and summary packets", () => {
	const reference = parseSiteExport(gpt41);
	for (const mutation of ["outcome", "condition", "cache"] as const) {
		const rows = structuredClone(summaryComparisons);
		const item = rows[1];
		assert.ok(item);
		const result = item.data.results[0];
		assert.ok(result);
		const unit = result.units[0];
		assert.ok(unit);
		if (mutation === "outcome") unit.outcome = unit.outcome === 0 ? 1 : 0;
		if (mutation === "condition") result.metadata.condition = "agentic";
		if (mutation === "cache") item.source.summary_cache_sha256 = "different";
		assert.throws(() => buildSupplementaryRows(rows, reference));
	}
});

test("summary diagnostics separate ranking from calibration", () => {
	const jev = supplementaryRows.find(
		(row) => row.slug === "jev-luna-summaries",
	);
	const lunaOff = supplementaryRows.find(
		(row) => row.slug === "gpt-6-luna-summaries-none",
	);
	const gpt41Row = supplementaryRows.find((row) => row.slug === "gpt-4-1");
	assert.ok(jev && lunaOff && gpt41Row);
	// Jev ranks cases nearly as well as Luna but its forecasts sit far below the base rate.
	assert.ok(Math.abs(jev.auc - 0.698) < 0.001);
	assert.ok(Math.abs(lunaOff.auc - 0.733) < 0.001);
	assert.ok(Math.abs(jev.mean_forecast - 0.305) < 0.001);
	assert.ok(jev.micro_brier > 0.25, "worse than always forecasting 50%");
	assert.ok(gpt41Row.auc < 0.5);
	assert.equal(jev.inference_usd, 0.044179);
	assert.equal(gpt41Row.inference_usd, null);
});

// Different summarization pipelines are separate conditions, while shared-packet
// controls must retain exactly the same frozen cache.
test("distinct summary packet groups remain labeled and outside the agentic ranking", () => {
	const rows = structuredClone(summaryComparisons);
	const item = rows[0];
	assert.ok(item);
	item.source.summary_packet_group = "separate-test-pipeline";
	item.source.summary_cache_sha256 = "different-frozen-cache";
	item.source.input_label = "Grok 4.6 shorter summaries · one shot";
	const result = buildSupplementaryRows(rows, parseSiteExport(gpt41));
	assert.equal(result[0]?.input_label, item.source.input_label);
});

test("Grok short condition retains protected scores and provider-reported inference cost", () => {
	const row = supplementaryRows.find(
		(r) => r.slug === "jev-grok-short-summaries",
	);
	assert.ok(row);
	assert.equal(row.micro_brier, 0.32725193798449614);
	assert.equal(row.equal_case_brier, 0.30504730523444806);
	assert.equal(row.inference_usd, 0.02015349);
	assert.equal(row.preparation_usd, 29.987453);
	assert.equal(row.input_label, "Grok 4.6 shorter summaries · one shot");
});
