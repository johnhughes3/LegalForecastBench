import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { parseManuscript, repositoryRootFrom } from "./manuscript.js";
import { PAPER, WORKING_PAPER_PDF } from "./paper.js";

const manuscriptFile = "docs/paper/LegalForecastBench-paper.tex";
const manuscriptPath = fileURLToPath(
	new URL(`../../../${manuscriptFile}`, import.meta.url),
);
const root = repositoryRootFrom(dirname(manuscriptPath));

test("a manuscript title and abstract become plain paragraphs", () => {
	const parsed = parseManuscript(String.raw`
\title{LegalForecastBench: Forecasting\\Judicial Decisions}
\begin{abstract}
% TODO: revise later
\draft{Claim--defendant units are 84.50\% accurate.

Second paragraph uses \emph{forecasting} and drops \citep{brier}.}
\end{abstract}
`);
	assert.equal(
		parsed.title,
		"LegalForecastBench: Forecasting Judicial Decisions",
	);
	assert.deepEqual(parsed.abstract, [
		"Claim–defendant units are 84.50% accurate.",
		"Second paragraph uses forecasting and drops.",
	]);
	assert.equal(parsed.abstractIsDraft, true);
	assert.equal(parsed.revisedOn, null);
});

test("TeX double quotes become typographic quotes", () => {
	const parsed = parseManuscript(
		"\\title{T}\n\\begin{abstract}\nSo-called ``legal experts'' aren't a tribunal.\n\\end{abstract}\n",
	);
	assert.deepEqual(parsed.abstract, [
		"So-called \u201clegal experts\u201d aren't a tribunal.",
	]);
});

test("the paper page reads the checked-in manuscript", () => {
	const parsed = parseManuscript(readFileSync(manuscriptPath, "utf8"));
	assert.equal(PAPER.title, parsed.title);
	assert.deepEqual(PAPER.abstract, parsed.abstract);
	assert.equal(PAPER.abstractIsDraft, parsed.abstractIsDraft);
	assert.equal(parsed.revisedOn, "2026-10-06");
	assert.equal(PAPER.revisedOn, parsed.revisedOn);
	assert.equal(PAPER.workingPdf, WORKING_PAPER_PDF);
	assert.match(parsed.title, /Legal Reasoning Ability$/);
	assert.equal(parsed.abstract.length, 5);
	assert.match(parsed.abstract[0] ?? "", /objectively verifiable rewards/);
	assert.match(parsed.abstract[1] ?? "", /erroneous rubrics/);
	assert.match(
		parsed.abstract[4] ?? "",
		/91 cases and 387 scored claim–defendant units/,
	);
	assert.match(parsed.abstract[4] ?? "", /84\.5%/);
	for (const paragraph of parsed.abstract) {
		assert.doesNotMatch(paragraph, /``|''/);
		assert.doesNotMatch(paragraph, /\\/);
	}
	assert.equal(
		existsSync(resolve(root, `site/public${WORKING_PAPER_PDF}`)),
		true,
	);
});

test("the manuscript is found from a bundled prerender path", () => {
	const bundled = fileURLToPath(
		new URL("../../../site/dist/.prerender/chunks/paper.mjs", import.meta.url),
	);
	const bundledRoot = repositoryRootFrom(dirname(bundled));
	assert.equal(bundledRoot, root);
	assert.equal(existsSync(resolve(bundledRoot, manuscriptFile)), true);
});
