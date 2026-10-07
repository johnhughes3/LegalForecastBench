import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { prefersMarkdown } from "./accept.js";
import { COPY } from "./copy.js";
import { FAQS } from "./faqs.js";
import { originUrl, REPO } from "./identity.js";
import {
	datasetNode,
	faqPageNode,
	jsonLdScript,
	organizationNode,
	pageGraph,
	personNode,
	scholarlyArticle,
	softwareSourceCodeNode,
} from "./jsonld.js";
import { lastmodFor } from "./lastmod.js";
import { llmsTxt } from "./llms.js";
import { mdxToMarkdown, stripJsxOutsideCode } from "./markdown.js";
import { markdownDestination, negotiationRewrites } from "./negotiate.js";
import { publicPaths } from "./paths.js";
import { AI_CRAWLERS, robotsTxt } from "./robots.js";
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
	assert.equal(lastmodFor("/paper/"), "2026-10-06");
	assert.equal(lastmodFor("/"), "2026-10-03");
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

test("project and author identities are distinct", () => {
	const project = organizationNode(originUrl());
	assert.deepEqual(project.sameAs, [
		"https://github.com/johnhughes3/LegalForecastBench",
	]);
	assert.ok(Array.isArray(personNode().sameAs));
	assert.notDeepEqual(project.sameAs, personNode().sameAs);
});

test("paper full text is associated with its article, without inventing a PDF", () => {
	const input = {
		headline: "Paper title",
		description: "Abstract",
		url: "https://www.legalforecastbench.org/paper/",
		authorName: "John J. Hughes, III",
	};
	assert.equal(scholarlyArticle(input).encoding, undefined);
	const pdfUrl = `${input.url}legalforecastbench-working.pdf`;
	assert.deepEqual(scholarlyArticle({ ...input, pdfUrl }).encoding, {
		"@type": "MediaObject",
		contentUrl: pdfUrl,
		encodingFormat: "application/pdf",
	});
});

/** Rules per user agent. Consecutive `User-agent` lines share one group. */
function robotsGroups(text: string): Map<string, string[]> {
	const groups = new Map<string, string[]>();
	let agents: string[] = [];
	let rules: string[] | undefined;
	for (const line of text.split("\n")) {
		const agent = /^User-agent: (.+)$/.exec(line)?.[1];
		if (agent) {
			if (rules) agents = [];
			rules = undefined;
			agents.push(agent);
		} else if (/^(Allow|Disallow): /.test(line)) {
			rules ??= [];
			for (const name of agents) groups.set(name, rules);
			rules.push(line);
		}
	}
	return groups;
}

test("robots names the AI crawlers and gives them the rules everyone gets", () => {
	const groups = robotsGroups(
		robotsTxt(new URL("https://www.legalforecastbench.org")),
	);
	const everyone = groups.get("*");
	assert.deepEqual(everyone, ["Allow: /", "Disallow: /agent/"]);
	for (const crawler of [
		"GPTBot",
		"OAI-SearchBot",
		"ChatGPT-User",
		"ClaudeBot",
		"Claude-SearchBot",
		"PerplexityBot",
		"Google-Extended",
		"Applebot-Extended",
		"CCBot",
	]) {
		assert.deepEqual(groups.get(crawler), everyone, crawler);
	}
	assert.equal(groups.size, AI_CRAWLERS.length + 1);
});

test("only the negotiation files carry a noindex header", () => {
	const vercel = JSON.parse(
		readFileSync(new URL("../../vercel.json", import.meta.url), "utf8"),
	) as { headers: { source: string; headers: { key: string }[] }[] };
	const tagged = vercel.headers
		.filter((rule) =>
			rule.headers.some((h) => h.key.toLowerCase() === "x-robots-tag"),
		)
		.map((rule) => rule.source);
	assert.deepEqual(tagged, ["/agent/(.*)"]);
});

test("llms.txt describes each page and links the data and citation files", () => {
	const text = llmsTxt([
		{
			slug: "results",
			path: "/results/",
			title: "Results",
			description: "Ranked scores.",
			markdown: "",
		},
	]);
	const site = "https://www.legalforecastbench.org";
	assert.ok(text.includes(`- [Results](${site}/results/): Ranked scores.`));
	for (const path of [
		"/data/current.json",
		"/data/significance/comparison.json",
		"/data/sources.json",
		"/data/costs.json",
		"/papers/legalforecastbench-working.pdf",
		"/lab/",
	]) {
		assert.ok(text.includes(`](${site}${path})`), path);
	}
	assert.ok(text.includes(`](${REPO}/blob/main/CITATION.cff)`));
});

test("the dataset lists its downloads and leaves the repository to its own node", () => {
	const url = "https://www.legalforecastbench.org/data/";
	const dataset = datasetNode({
		name: "LegalForecastBench results",
		description: "Forecasts scored against the actual rulings.",
		url,
		temporalCoverage: "2026-06-30/2026-08-07",
		version: "cycle-1",
		dateModified: "2026-10-03",
		downloads: [
			{ name: "Ranked results", contentUrl: `${url}current.json` },
			{ name: "Cost evidence", contentUrl: `${url}costs.json` },
		],
	});
	assert.equal(dataset.codeRepository, undefined);
	assert.equal(dataset.version, "cycle-1");
	assert.equal(dataset.license, "https://creativecommons.org/licenses/by/4.0/");
	assert.deepEqual(dataset.distribution, [
		{
			"@type": "DataDownload",
			name: "Ranked results",
			encodingFormat: "application/json",
			contentUrl: `${url}current.json`,
		},
		{
			"@type": "DataDownload",
			name: "Cost evidence",
			encodingFormat: "application/json",
			contentUrl: `${url}costs.json`,
		},
	]);
	assert.ok(Array.isArray(dataset.variableMeasured));
	const code = softwareSourceCodeNode();
	assert.equal(code.codeRepository, REPO);
	assert.equal(code.license, "https://www.apache.org/licenses/LICENSE-2.0");
});
