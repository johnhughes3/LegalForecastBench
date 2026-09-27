import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { parseCitation, toApa, toBibtex } from "./citation.js";

const cff = readFileSync(
	new URL("../../../CITATION.cff", import.meta.url),
	"utf8",
);

test("the repository CITATION.cff parses into the rendered citation", () => {
	const c = parseCitation(cff);
	assert.ok(c.title.length > 0);
	assert.match(c.year, /^\d{4}$/);
	assert.ok(c.authors.length > 0);
	assert.ok(c.url?.startsWith("https://"));
});

test("citations format suffixes and versions in BibTeX and APA style", () => {
	const c = parseCitation(`
title: "Example Bench"
version: "1.2.0"
date-released: 2026-05-17
url: "https://example.org"
authors:
  - family-names: "Doe"
    given-names: "Jane Q."
    name-suffix: "Jr."
  - family-names: "Roe"
    given-names: "Rick"
`);
	assert.equal(
		toBibtex(c),
		[
			"@software{doe2026examplebench,",
			"  author = {Doe, Jr., Jane Q. and Roe, Rick},",
			"  title = {{Example Bench}},",
			"  version = {1.2.0},",
			"  year = {2026},",
			"  date = {2026-05-17},",
			"  url = {https://example.org},",
			"}",
		].join("\n"),
	);
	assert.equal(
		toApa(c),
		"Doe, J. Q., Jr., & Roe, R. (2026). Example Bench (Version 1.2.0) [Computer software]. https://example.org",
	);
});
