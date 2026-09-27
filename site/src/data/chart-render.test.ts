import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ConfidenceChart from "../components/ConfidenceChart";
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
