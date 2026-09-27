import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ConfidenceChart from "../components/ConfidenceChart";
import Leaderboard from "../components/Leaderboard";
import ParetoChart from "../components/ParetoChart";
import { snapshot } from "./results";

test("confidence chart does not move a low-accuracy point to the old 85% floor", () => {
	const data = structuredClone(snapshot);
	const model = data.models[0];
	assert.ok(model);
	model.high_confidence = { count: 10, wrong: 4, mean_confidence: 0.95 };
	data.models = [model];
	const html = renderToStaticMarkup(
		createElement(ConfidenceChart, { snapshot: data }),
	);
	assert.match(html, /realized accuracy 60.0%/);
	assert.match(html, /left:60%/);
	assert.match(html, /Full 0–100% axis/);
});

test("cost chart includes all priced models and keeps outlier grid readable", () => {
	const data = structuredClone(snapshot);
	// Exercise an expanded cost census independently of accounting availability.
	for (const [index, model] of data.models.entries())
		model.cost.usd = index + 1;
	const html = renderToStaticMarkup(
		createElement(ParetoChart, { snapshot: data }),
	);
	for (const model of data.models)
		assert.ok(html.includes(`/models/${model.slug}/`), model.slug);
	assert.match(html, /16 plotted models/);
	assert.ok((html.match(/stroke="var\(--chart-grid\)"/g) ?? []).length <= 16);
	assert.ok(!html.includes("NaN"));
	assert.ok(html.includes("GPT-4.1"));
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
