import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { parseManuscript } from "./manuscript.js";
import { PAPER, WORKING_PAPER_PDF } from "./paper.js";

const manuscriptPath = fileURLToPath(
	new URL("../../../docs/paper/LegalForecastBench-paper.tex", import.meta.url),
);

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
});

test("the paper page reads the checked-in manuscript", () => {
	const parsed = parseManuscript(readFileSync(manuscriptPath, "utf8"));
	assert.equal(PAPER.title, parsed.title);
	assert.deepEqual(PAPER.abstract, parsed.abstract);
	assert.equal(PAPER.abstractIsDraft, parsed.abstractIsDraft);
	assert.equal(PAPER.workingPdf, WORKING_PAPER_PDF);
	assert.match(parsed.title, /Legal Reasoning Ability$/);
	assert.equal(parsed.abstract.length, 1);
	assert.match(parsed.abstract[0] ?? "", /claim–defendant-level/);
	assert.match(parsed.abstract[0] ?? "", /84\.50%/);
	assert.doesNotMatch(parsed.abstract[0] ?? "", /\\/);
	assert.equal(
		existsSync(
			fileURLToPath(
				new URL(`../../public${WORKING_PAPER_PDF}`, import.meta.url),
			),
		),
		true,
	);
});
