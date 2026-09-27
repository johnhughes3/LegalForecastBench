import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ConfidenceChart from "../components/ConfidenceChart";
import Leaderboard from "../components/Leaderboard";
import ParetoChart from "../components/ParetoChart";
import { primarySnapshot, REFERENCE_SLUGS, snapshot } from "./results";

test("confidence chart extends its axis to a low-accuracy point instead of clamping it", () => {
	const data = structuredClone(snapshot);
	const model = data.models[0];
	assert.ok(model);
	model.high_confidence = { count: 10, wrong: 4, mean_confidence: 0.95 };
	data.models = [model];
	const html = renderToStaticMarkup(
		createElement(ConfidenceChart, { snapshot: data }),
	);
	assert.match(html, /realized accuracy 60.0%/);
	// The axis starts at 55%, so 60% sits a ninth of the way in, not at the floor.
	assert.match(html, />55%</);
	assert.match(html, /left:11\.1\d*%/);
});

test("reference models are excluded from the ranked set, and the chart plots and labels the rest", () => {
	assert.ok(REFERENCE_SLUGS.has("gpt-4-1"));
	assert.ok(!primarySnapshot.models.some((m) => m.slug === "gpt-4-1"));
	assert.equal(
		primarySnapshot.models.length,
		snapshot.models.length - REFERENCE_SLUGS.size,
	);
	const data = structuredClone(primarySnapshot);
	for (const [index, model] of data.models.entries())
		model.cost.usd = index + 1;
	const html = renderToStaticMarkup(
		createElement(ParetoChart, { snapshot: data }),
	);
	for (const model of data.models) {
		assert.ok(html.includes(`/models/${model.slug}/`), model.slug);
		// Desktop rendering labels every point.
		assert.ok(
			html.includes(`>${model.display_name}</text>`),
			model.display_name,
		);
	}
	assert.ok(!html.includes("NaN"));
});

test("display names are reader-facing, without run settings", () => {
	for (const model of snapshot.models) {
		assert.doesNotMatch(
			model.display_name,
			/agentic|via |snapshot|reasoning/i,
			model.slug,
		);
		assert.doesNotMatch(model.eligibility_reason, /^[a-z_]+$/, model.slug);
	}
});

test("leaderboard Pareto badges name the qualifying metrics", () => {
	const html = renderToStaticMarkup(createElement(Leaderboard, { snapshot }));
	const rows = html.match(/<tr[\s\S]*?<\/tr>/g) ?? [];
	const labeled = rows.filter((row) => row.includes("Pareto frontier"));
	assert.equal(labeled.length, 3);
	for (const slug of ["gpt-6-luna", "gpt-5-6-luna", "gpt-6-sol"])
		assert.ok(
			labeled.some((row) => row.includes(`/models/${slug}/`)),
			slug,
		);
});

test("a model on only the accuracy frontier gets an accuracy-specific tooltip", () => {
	const data = structuredClone(snapshot);
	data.models = data.models.slice(0, 2);
	const [a, b] = data.models;
	assert.ok(a && b);
	a.cost.usd = b.cost.usd = 1;
	a.micro_brier = a.equal_case_brier = 0.1;
	b.micro_brier = b.equal_case_brier = 0.2;
	a.correct = 200;
	b.correct = 300;
	const html = renderToStaticMarkup(
		createElement(Leaderboard, { snapshot: data }),
	);
	const row = (html.match(/<tr[\s\S]*?<\/tr>/g) ?? []).find((row) =>
		row.includes(`/models/${b.slug}/`),
	);
	assert.ok(row);
	assert.match(row, /Pareto frontier for: Unit accuracy\./);
	assert.ok(!row.includes("Pareto frontier for: Micro Brier"));
});
