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
	assert.equal(supplementaryRows.length, 4);
	assert.equal(summaryComparisons.length, 3);
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
	assert.equal(snapshot.models.length, 16);
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
