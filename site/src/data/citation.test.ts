import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
	parseCitation,
	parsePaperCitation,
	toApa,
	toBibtex,
	toPaperApa,
	toPaperBibtex,
} from "./citation.js";
import { PAPER } from "./paper.js";

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

test("the preferred citation is the paper the manuscript and the site describe", () => {
	const paper = parsePaperCitation(cff);
	assert.equal(paper.title, PAPER.title);
	assert.equal(paper.url, "https://www.legalforecastbench.org/paper/");
	assert.equal(PAPER.publishedOn, paper.date);
	assert.match(paper.date, /^\d{4}-\d{2}-\d{2}$/);
	// No identifier is claimed until the paper has one.
	assert.equal(paper.doi, null);
	const software = parseCitation(cff);
	assert.deepEqual(paper.authors, software.authors);
	assert.notEqual(toPaperBibtex(paper), toBibtex(software));
});

const paperCff = (extra = "") => `
title: "Example Bench"
date-released: 2026-05-17
authors:
  - family-names: "Doe"
    given-names: "Jane Q."
preferred-citation:
  type: generic
  title: "Example Bench: A Study"
  authors:
    - family-names: "Doe"
      given-names: "Jane Q."
      name-suffix: "Jr."
  year: 2026
  month: 6
  date-published: 2026-06-02
  notes: "Working paper"
  url: "https://example.org/paper/"
${extra}`;

test("a paper citation is a misc entry, and a DOI is one added line", () => {
	const paper = parsePaperCitation(paperCff());
	assert.equal(
		toPaperBibtex(paper),
		[
			"@misc{doe2026example,",
			"  author = {Doe, Jr., Jane Q.},",
			"  title = {{Example Bench: A Study}},",
			"  year = {2026},",
			"  date = {2026-06-02},",
			"  note = {Working paper},",
			"  url = {https://example.org/paper/},",
			"}",
		].join("\n"),
	);
	assert.equal(
		toPaperApa(paper),
		"Doe, J. Q., Jr. (2026). Example Bench: A Study [Working paper]. https://example.org/paper/",
	);
	const withDoi = parsePaperCitation(paperCff('  doi: "10.1234/example"'));
	assert.match(toPaperBibtex(withDoi), / {2}doi = \{10\.1234\/example\},/);
	assert.match(toPaperApa(withDoi), /https:\/\/doi\.org\/10\.1234\/example$/);
});

test("a publication date that disagrees with its year or month is rejected", () => {
	assert.throws(
		() => parsePaperCitation(paperCff().replace("month: 6", "month: 7")),
		/year and month must match/,
	);
});
