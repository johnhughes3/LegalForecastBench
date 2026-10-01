import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { prefersMarkdown } from "./accept.js";
import { COPY } from "./copy.js";
import { FAQS } from "./faqs.js";
import { originUrl } from "./identity.js";
import { faqPageNode, jsonLdScript, pageGraph } from "./jsonld.js";
import { lastmodFor } from "./lastmod.js";
import { llmsTxt } from "./llms.js";
import { mdxToMarkdown, stripJsxOutsideCode } from "./markdown.js";
import { markdownDestination, negotiationRewrites } from "./negotiate.js";
import { publicPaths } from "./paths.js";
import { robotsTxt } from "./robots.js";
import { includeInSitemap } from "./sitemap.js";
import { documentTitle, TITLE_LIMIT } from "./titles.js";

test("page titles stay within the branded limit", () => {
	for (const page of Object.values(COPY)) {
		assert.ok(documentTitle(page.title).length <= TITLE_LIMIT, page.title);
	}
	assert.equal(documentTitle(), "LegalForecastBench");
	assert.equal(
		documentTitle("Confident misses: why sharp forecasters lost points"),
		"Confident misses: why sharp forecasters lost points",
	);
});

test("markdown is negotiated only when it outranks HTML", () => {
	assert.equal(prefersMarkdown("text/markdown"), true);
	assert.equal(prefersMarkdown("text/plain"), true);
	assert.equal(prefersMarkdown("text/markdown, text/html;q=0.5"), true);
	assert.equal(
		prefersMarkdown(
			"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
		),
		false,
	);
	assert.equal(
		prefersMarkdown("text/html,application/xhtml+xml,text/plain,*/*"),
		false,
	);
	assert.equal(prefersMarkdown(null), false);
});

test("vercel rewrites match the negotiation table and every public page", () => {
	const vercel = JSON.parse(
		readFileSync(new URL("../../vercel.json", import.meta.url), "utf8"),
	) as { rewrites: unknown };
	assert.deepEqual(vercel.rewrites, negotiationRewrites());
	for (const doc of publicPaths()) {
		assert.equal(
			markdownDestination(doc.path, "text/markdown"),
			`/agent/${doc.slug}.md`,
		);
		assert.equal(markdownDestination(doc.path, "text/html"), null);
	}
	assert.equal(
		markdownDestination("/data/current.json", "text/markdown"),
		null,
	);
	assert.equal(markdownDestination("/llms.txt", "text/plain"), null);
});

test("llms.txt lists canonical pages and not agent URLs", () => {
	const text = llmsTxt(
		publicPaths().map((doc) => ({
			...doc,
			title: doc.slug,
			description: "",
			markdown: "",
		})),
	);
	assert.match(text, /Accept: text\/markdown/);
	assert.doesNotMatch(text, /\/agent\//);
	assert.match(text, /https:\/\/www\.legalforecastbench\.org\/results\//);
	assert.doesNotMatch(text, /\.md\)/);
});

test("mdx cleanup keeps code and drops components", () => {
	const source = `---
title: Example
---
import Chart from "./Chart";

See \`<InlineCTA />\` and a fence:

\`\`\`\`md
\`\`\`
not closed by the shorter fence
\`\`\`
\`\`\`\`

<Chart />
<Note>Keep this</Note>
`;
	const markdown = mdxToMarkdown(source);
	assert.match(markdown, /<InlineCTA \/>/);
	assert.match(markdown, /```\nnot closed/);
	assert.doesNotMatch(markdown, /import Chart/);
	assert.match(markdown, /Keep this/);
	assert.doesNotMatch(markdown, /<Note>/);
	assert.equal(stripJsxOutsideCode("`<b>` stays"), "`<b>` stays");
});

test("sitemap skips agent files and uses real dates", () => {
	const site = "https://www.legalforecastbench.org";
	assert.equal(includeInSitemap(`${site}/results/`), true);
	assert.equal(includeInSitemap(`${site}/agent/results`), false);
	assert.equal(includeInSitemap(`${site}/llms.txt`), false);
	assert.equal(includeInSitemap(`${site}/data/current.json`), false);
	assert.equal(includeInSitemap(`${site}/og/home.png`), false);
	assert.equal(lastmodFor("/paper/"), "2026-10-01");
	assert.equal(lastmodFor("/"), "2026-09-27");
	assert.equal(lastmodFor("/findings/confident-misses/"), "2026-09-27");
});

test("robots allows the site and hides negotiation files", () => {
	const text = robotsTxt(new URL("https://www.legalforecastbench.org"));
	assert.match(text, /Allow: \//);
	assert.match(text, /Disallow: \/agent\//);
	assert.match(
		text,
		/Sitemap: https:\/\/www\.legalforecastbench\.org\/sitemap-index\.xml/,
	);
});

test("the homepage graph cites the visible FAQ and the organization", () => {
	const canonical = new URL("/", originUrl()).href;
	const graph = pageGraph({
		site: originUrl(),
		canonical,
		title: documentTitle(COPY.home.title),
		description: COPY.home.description,
		image: "https://www.legalforecastbench.org/og/home.png",
		crumbs: [],
		extra: [faqPageNode(canonical, FAQS)],
	});
	const serialized = jsonLdScript(graph);
	assert.match(serialized, /"@type":"Organization"/);
	assert.match(serialized, /"@type":"FAQPage"/);
	assert.match(serialized, /Are the published forecasts legal advice\?/);
	assert.match(serialized, /https:\/\/x\.com\/jjhughes3/);
	assert.match(serialized, /https:\/\/www\.linkedin\.com\/in\/jhughes3/);
	assert.doesNotMatch(serialized, /sameAs":\[\]/);
	assert.equal(serialized.includes("<"), false);
	for (const faq of FAQS) {
		assert.match(serialized, new RegExp(faq.question.replaceAll("?", "\\?")));
	}
});
