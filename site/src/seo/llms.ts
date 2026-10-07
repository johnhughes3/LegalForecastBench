import { WORKING_PAPER_PDF } from "../data/paper.js";
import type { AgentDocument } from "./agent-document.js";
import { absoluteUrl, REPO } from "./identity.js";

/** `- [title](url): description`, the entry form the llms.txt convention uses. */
function entry(title: string, url: string, description: string): string {
	return description
		? `- [${title}](${url}): ${description}`
		: `- [${title}](${url})`;
}

/** Downloads and citation files the Data and paper pages already link. */
function resources(): string[] {
	return [
		entry(
			"Ranked results (JSON)",
			absoluteUrl("/data/current.json"),
			"Scores, eligibility, costs, and significance for the current release.",
		),
		entry(
			"Paired significance analysis (JSON)",
			absoluteUrl("/data/significance/comparison.json"),
			"Bootstrap confidence intervals for every tested pair.",
		),
		entry(
			"Run and release provenance (JSON)",
			absoluteUrl("/data/sources.json"),
			"",
		),
		entry("Cost evidence (JSON)", absoluteUrl("/data/costs.json"), ""),
		entry("Working paper (PDF)", absoluteUrl(WORKING_PAPER_PDF), ""),
		entry(
			"Source code",
			REPO,
			"Benchmark code, prompts, scorer, and model registries.",
		),
		entry(
			"CITATION.cff",
			`${REPO}/blob/main/CITATION.cff`,
			"How to cite the benchmark.",
		),
	];
}

export function llmsTxt(docs: readonly AgentDocument[]): string {
	const lines = [
		"# LegalForecastBench",
		"",
		"> An open benchmark measuring whether frontier AI models can forecast how federal judges rule on motions to dismiss.",
		"",
		"## For AI agents",
		"",
		"Each page below links to its markdown copy. The `Canonical:` line at the top of each copy gives the HTML page to cite.",
		"",
		`Every copy in one file: ${absoluteUrl("/llms-full.txt")}`,
		`Sitemap: ${absoluteUrl("/sitemap-index.xml")}`,
		"",
		"## Pages",
		"",
	];
	for (const doc of docs) {
		lines.push(
			entry(doc.title, absoluteUrl(`/agent/${doc.slug}.md`), doc.description),
		);
	}
	lines.push(
		"",
		"## Data and citation",
		"",
		"The data is licensed under CC BY 4.0 and the code under the Apache License 2.0.",
		"",
		...resources(),
		"",
	);
	return lines.join("\n");
}

export function llmsFullTxt(docs: readonly AgentDocument[]): string {
	return `${docs.map((doc) => doc.markdown.trim()).join("\n\n---\n\n")}\n`;
}
