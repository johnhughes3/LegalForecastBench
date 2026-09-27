import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import EligibilityBadge from "../components/EligibilityBadge";
import Leaderboard from "../components/Leaderboard";
import { snapshot } from "./results";

test("sort buttons carry their own tooltip description without nested buttons", () => {
	const html = renderToStaticMarkup(createElement(Leaderboard, { snapshot }));
	for (const label of [
		"Micro Brier",
		"Equal-case",
		"Accuracy",
		"≥90% misses",
		"Cost",
	]) {
		assert.match(
			html,
			new RegExp(`<button[^>]*aria-describedby="[^"]+"[^>]*>${label}`),
		);
	}
	assert.doesNotMatch(html, /<button[^>]*>(?:(?!<\/button>)[\s\S])*<button/);
});

test("unknown eligibility describes missing classification, not qualified status", () => {
	const html = renderToStaticMarkup(
		createElement(EligibilityBadge, {
			eligibility: "unknown",
			reason: "No classification supplied.",
		}),
	);
	assert.match(html, /Unknown:/);
	assert.doesNotMatch(html, /Qualified:/);
});
