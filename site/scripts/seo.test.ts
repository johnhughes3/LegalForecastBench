import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

import { PAPER } from "../src/data/paper";
import { SITE_ORIGIN } from "../src/seo/identity";

test("built paper exposes Scholar metadata, one same-directory PDF, and both citations", () => {
	const html = readFileSync("dist/paper/index.html", "utf8");
	const metadata = new Map(
		[...html.matchAll(/<meta name="([^"]+)" content="([^"]*)"/g)].map(
			(match) => [match[1], match[2]],
		),
	);
	assert.equal(metadata.get("citation_author"), "Hughes III, John J.");
	assert.ok(metadata.get("citation_title"));
	assert.match(
		metadata.get("citation_publication_date") ?? "",
		/^\d{4}\/\d{2}\/\d{2}$/,
	);
	assert.equal(
		metadata.get("citation_publication_date"),
		PAPER.publishedOn.replaceAll("-", "/"),
	);
	const abstractUrl = new URL(metadata.get("citation_abstract_html_url") ?? "");
	const pdfUrl = new URL(metadata.get("citation_pdf_url") ?? "");
	assert.equal(pdfUrl.origin, abstractUrl.origin);
	assert.equal(
		pdfUrl.pathname,
		`${abstractUrl.pathname}legalforecastbench-working.pdf`,
	);
	assert.equal(pdfUrl.pathname, PAPER.workingPdf);
	assert.ok(existsSync(`dist${pdfUrl.pathname}`));
	// One copy of the PDF: the earlier /papers/ path is a redirect, not a file.
	assert.equal(existsSync("dist/papers"), false);
	assert.ok(html.includes(`href="${PAPER.workingPdf}"`));
	const article = html.match(/"@type":"ScholarlyArticle".*?"inLanguage"/)?.[0];
	assert.ok(article?.includes(`"datePublished":"${PAPER.publishedOn}"`));
	assert.ok(html.includes("@misc{"));
	assert.ok(html.includes("@software{"));
	assert.equal(metadata.get("robots"), "max-image-preview:large");
	assert.ok(metadata.get("twitter:image:alt"));
	const home = readFileSync("dist/index.html", "utf8");
	assert.doesNotMatch(home, /name="citation_title"/);
});

test("every site link in the built llms.txt resolves to a built file", () => {
	const text = readFileSync("dist/llms.txt", "utf8");
	const links = [...text.matchAll(/\]\(([^)\s]+)\)/g)]
		.map((match) => match[1] ?? "")
		.filter((url) => url.startsWith(SITE_ORIGIN));
	assert.ok(links.length > 10);
	for (const url of links) {
		const path = new URL(url).pathname;
		const file = path.endsWith("/") ? `${path}index.html` : path;
		assert.ok(existsSync(`dist${file}`), url);
	}
});

test("every page that names a markdown copy has one in the build", () => {
	for (const page of ["index.html", "data/index.html", "paper/index.html"]) {
		const html = readFileSync(`dist/${page}`, "utf8");
		const href = html.match(
			/<link rel="alternate" type="text\/markdown" href="([^"]+)"/,
		)?.[1];
		assert.ok(href && existsSync(`dist${href}`), page);
	}
	assert.doesNotMatch(
		readFileSync("dist/data/historical-results/index.html", "utf8"),
		/type="text\/markdown"/,
	);
});
