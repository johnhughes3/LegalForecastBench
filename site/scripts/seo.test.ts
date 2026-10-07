import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { AUTHOR } from "../src/data/author";
import { currentPaper, PAPER } from "../src/data/paper";

test("built paper exposes Scholar metadata and identical same-directory full text", () => {
	const html = readFileSync("dist/paper/index.html", "utf8");
	const metadata = new Map(
		[...html.matchAll(/<meta name="([^"]+)" content="([^"]*)"/g)].map(
			(match) => [match[1], match[2]],
		),
	);
	assert.equal(metadata.get("citation_author"), AUTHOR.name);
	assert.ok(metadata.get("citation_title"));
	assert.match(
		metadata.get("citation_publication_date") ?? "",
		/^\d{4}\/\d{2}\/\d{2}$/,
	);
	assert.equal(
		metadata.get("citation_publication_date"),
		(currentPaper?.date ?? PAPER.revisedOn)?.replaceAll("-", "/"),
	);
	const abstractUrl = new URL(metadata.get("citation_abstract_html_url") ?? "");
	const pdfUrl = new URL(metadata.get("citation_pdf_url") ?? "");
	assert.equal(pdfUrl.origin, abstractUrl.origin);
	assert.equal(
		pdfUrl.pathname,
		`${abstractUrl.pathname}legalforecastbench-working.pdf`,
	);
	assert.deepEqual(
		readFileSync(`dist${pdfUrl.pathname}`),
		readFileSync(`public${PAPER.workingPdf}`),
	);
	assert.equal(metadata.get("robots"), "max-image-preview:large");
	assert.ok(metadata.get("twitter:image:alt"));
	const home = readFileSync("dist/index.html", "utf8");
	assert.doesNotMatch(home, /name="citation_title"/);
});
