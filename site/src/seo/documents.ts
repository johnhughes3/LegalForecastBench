import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { analysisItems } from "../data/analysis.js";
import {
	APPROACH_COMPARISON,
	APPROACH_HEADING,
	APPROACH_LEAD,
	APPROACH_PIPELINE,
} from "../data/approach.js";
import { AUTHOR, REPO } from "../data/author.js";
import { comparison, comparisonScope } from "../data/comparison.js";
import { publishedFindings } from "../data/findings.js";
import { repositoryRoot } from "../data/manuscript.js";
import { formatPercent } from "../data/metrics.js";
import { PAPER } from "../data/paper.js";
import { primarySnapshot, snapshot } from "../data/results.js";
import { supplementaryRows } from "../data/supplementary-results.js";
import type { AgentDocument } from "./agent-document.js";
import { COPY } from "./copy.js";
import { FAQS } from "./faqs.js";
import { absoluteUrl } from "./identity.js";
import { mdxToMarkdown } from "./markdown.js";

export type { AgentDocument } from "./agent-document.js";
export { llmsFullTxt, llmsTxt } from "./llms.js";

function header(title: string, description: string, path: string): string {
	return [
		`# ${title}`,
		"",
		`> ${description}`,
		"",
		`Canonical: ${absoluteUrl(path)}`,
		"",
	].join("\n");
}

function homeMarkdown(): string {
	const { cohort } = snapshot;
	const lines = [
		header(COPY.home.title, COPY.home.description, "/"),
		`The current release scores ${cohort.case_count} federal cases and ${cohort.unit_count} claim-defendant units. ${formatPercent(cohort.dismissed_unit_count / cohort.unit_count)} of units were fully dismissed.`,
		"",
		"## Frequently asked questions",
		"",
	];
	for (const faq of FAQS) {
		lines.push(`### ${faq.question}`, "", faq.answer, "");
		if (faq.href && faq.hrefLabel) {
			lines.push(`[${faq.hrefLabel}](${absoluteUrl(faq.href)})`, "");
		}
	}
	lines.push(
		"Send `Accept: text/markdown` against any page URL for markdown at that same address.",
		"",
	);
	return lines.join("\n");
}

function resultsMarkdown(): string {
	const ranked = [...primarySnapshot.models].sort(
		(a, b) => a.micro_brier - b.micro_brier,
	);
	const n = snapshot.cohort.unit_count;
	const lines = [
		header(COPY.results.title, COPY.results.description, "/results/"),
		"Lower micro Brier is better. Summary-pipeline conditions are a separate experiment and are not in this table.",
		"",
		`A constant 50% forecast scores ${snapshot.cohort.constant_forecast_micro_brier.toFixed(3)} micro Brier.`,
		"",
		"| Model | Micro Brier | Equal-case Brier | Accuracy | Eligibility |",
		"| --- | --- | --- | --- | --- |",
	];
	for (const model of ranked) {
		lines.push(
			`| [${model.display_name}](${absoluteUrl(`/models/${model.slug}/`)}) | ${model.micro_brier.toFixed(4)} | ${model.equal_case_brier.toFixed(4)} | ${formatPercent(model.correct / n)} | ${model.eligibility} |`,
		);
	}
	lines.push("");
	return lines.join("\n");
}

function modelMarkdown(slug: string): string {
	const model = snapshot.models.find((item) => item.slug === slug);
	if (!model) throw new Error(`Missing model ${slug}`);
	const n = snapshot.cohort.unit_count;
	const description = `${model.display_name} on LegalForecastBench: micro Brier ${model.micro_brier.toFixed(4)} across ${n} units.`;
	return [
		header(model.display_name, description, `/models/${slug}/`),
		`- Provider: ${model.provider}`,
		`- Reasoning: ${model.reasoning}`,
		`- Public release: ${model.release_date}`,
		`- Training cutoff: ${model.training_cutoff ?? "Not disclosed"}`,
		`- Eligibility: ${model.eligibility}. ${model.eligibility_reason}`,
		`- Micro Brier: ${model.micro_brier.toFixed(4)}`,
		`- Equal-case Brier: ${model.equal_case_brier.toFixed(4)}`,
		`- Accuracy: ${formatPercent(model.correct / n)} (${model.correct} of ${n})`,
		`- High-confidence predictions: ${model.high_confidence.count}, of which ${model.high_confidence.wrong} were wrong`,
		"",
		`Ranked comparison: ${absoluteUrl("/results/")}`,
		"",
	].join("\n");
}

function methodsMarkdown(): string {
	const source = readFileSync(
		resolve(repositoryRoot(), "docs/METHODS.md"),
		"utf8",
	);
	// Sibling docs are not site pages. Point at the repository, as the HTML page does.
	const repoDocs =
		"https://github.com/johnhughes3/LegalForecastBench/blob/main/docs/";
	const linked = source.replace(
		/\]\((?!https?:|#|\/|mailto:)([^)]+)\)/g,
		(_match, target: string) => `](${new URL(target, repoDocs).href})`,
	);
	return [
		header(COPY.methods.title, COPY.methods.description, "/methods/"),
		"The HTML page opens with a short summary computed from the published snapshot. The technical methods follow.",
		"",
		linked.trim(),
		"",
	].join("\n");
}

function paperMarkdown(): string {
	const lines = [
		header(PAPER.title, COPY.paper.description, "/paper/"),
		`${PAPER.status} by ${PAPER.author}.`,
		"",
	];
	if (PAPER.revisedOn) lines.push(`Manuscript date: ${PAPER.revisedOn}`, "");
	lines.push(
		"## Abstract",
		"",
		...PAPER.abstract.flatMap((paragraph) => [paragraph, ""]),
	);
	lines.push(`PDF: ${absoluteUrl(PAPER.workingPdf)}`, "");
	return lines.join("\n");
}

async function analysisMarkdown(): Promise<string> {
	const items = await analysisItems();
	const lines = [
		header(COPY.analysis.title, COPY.analysis.description, "/analysis/"),
	];
	for (const item of items) {
		const href = item.external ? item.href : absoluteUrl(item.href);
		lines.push(`- [${item.title}](${href}) — ${item.summary}`);
	}
	lines.push("");
	return lines.join("\n");
}

function approachMarkdown(): string {
	const lines = [
		header(APPROACH_HEADING, COPY.approach.description, "/approach/"),
		APPROACH_LEAD,
		"",
		"## From public filings to a checkable signal",
		"",
	];
	for (const step of APPROACH_PIPELINE) {
		lines.push(`- **${step.step}.** ${step.body}`);
	}
	lines.push(
		"",
		"## Outcome grading and rubric grading",
		"",
		"| | Outcome grading | Rubric grading |",
		"| --- | --- | --- |",
	);
	for (const [dimension, outcome, rubric] of APPROACH_COMPARISON) {
		lines.push(`| ${dimension} | ${outcome} | ${rubric} |`);
	}
	lines.push(
		"",
		"The HTML page also discusses five ways a rubric answer key can fail, with examples from two public Harvey LAB tasks, and the limits of outcome grading.",
		"",
		`Author: ${AUTHOR.name}`,
		"",
	);
	return lines.join("\n");
}

function experimentMarkdown(): string {
	const lines = [
		header(
			COPY.experiment.title,
			COPY.experiment.description,
			"/experiments/summary-pipelines/",
		),
		"These conditions forecast from the same case summaries. They are not part of the full-document ranking.",
		"",
		"| Condition | Micro Brier | Equal-case Brier | Accuracy |",
		"| --- | --- | --- | --- |",
	];
	for (const row of supplementaryRows) {
		lines.push(
			`| ${row.display_name} (${row.reasoning_label}) | ${row.micro_brier.toFixed(4)} | ${row.equal_case_brier.toFixed(4)} | ${formatPercent(row.correct / row.unit_count)} |`,
		);
	}
	lines.push(
		"",
		`Constant-forecast micro Brier on the main cohort: ${snapshot.cohort.constant_forecast_micro_brier.toFixed(3)}.`,
		"",
	);
	return lines.join("\n");
}

function dataMarkdown(): string {
	const { cohort, provenance } = snapshot;
	return [
		header(COPY.data.title, COPY.data.description, "/data/"),
		`Forecasts by ${snapshot.models.length} model configurations of whether each challenged claim in ${cohort.case_count} federal motions to dismiss would be fully dismissed, scored against the actual rulings (${cohort.unit_count} claim-defendant units).`,
		"",
		`- Release: ${provenance.release}`,
		`- Main results JSON: ${absoluteUrl("/data/current.json")}`,
		`- Significance JSON: ${absoluteUrl("/data/significance/comparison.json")}`,
		`- Cost evidence: ${absoluteUrl("/data/costs.json")}`,
		`- Data license: https://creativecommons.org/licenses/by/4.0/`,
		`- Code license: Apache License 2.0`,
		`- Source: ${REPO}`,
		"",
	].join("\n");
}

function runNotesMarkdown(): string {
	const notes = snapshot.models
		.filter((model) => model.cost.note)
		.map((model) => `- **${model.display_name}.** ${model.cost.note}`);
	return [
		header(COPY.runNotes.title, COPY.runNotes.description, "/data/run-notes/"),
		snapshot.provenance.method,
		"",
		comparisonScope,
		comparison.caveat,
		"Untested pairs are not evidence of equivalence.",
		"",
		"Charts compare estimated standard-rate costs for the same successful workload. They do not represent total experiment spending or provider invoices.",
		"",
		...notes,
		"",
	].join("\n");
}

function findingsDirectory(): string {
	return resolve(repositoryRoot(), "site/src/content/findings");
}

function findingSource(id: string): string {
	for (const ext of [".mdx", ".md"]) {
		const path = resolve(findingsDirectory(), `${id}${ext}`);
		if (existsSync(path)) return readFileSync(path, "utf8");
	}
	throw new Error(`Missing finding source for ${id}`);
}

export async function agentDocuments(): Promise<AgentDocument[]> {
	const findings = await publishedFindings();
	const docs: AgentDocument[] = [
		{
			slug: "home",
			path: "/",
			title: COPY.home.title,
			description: COPY.home.description,
			markdown: homeMarkdown(),
		},
		{
			slug: "results",
			path: "/results/",
			title: COPY.results.title,
			description: COPY.results.description,
			markdown: resultsMarkdown(),
		},
		{
			slug: "methods",
			path: "/methods/",
			title: COPY.methods.title,
			description: COPY.methods.description,
			markdown: methodsMarkdown(),
		},
		{
			slug: "paper",
			path: "/paper/",
			title: PAPER.title,
			description: COPY.paper.description,
			markdown: paperMarkdown(),
		},
		{
			slug: "analysis",
			path: "/analysis/",
			title: COPY.analysis.title,
			description: COPY.analysis.description,
			markdown: await analysisMarkdown(),
		},
		{
			slug: "approach",
			path: "/approach/",
			title: APPROACH_HEADING,
			description: COPY.approach.description,
			markdown: approachMarkdown(),
		},
		{
			slug: "experiments/summary-pipelines",
			path: "/experiments/summary-pipelines/",
			title: COPY.experiment.title,
			description: COPY.experiment.description,
			markdown: experimentMarkdown(),
		},
		{
			slug: "data",
			path: "/data/",
			title: COPY.data.title,
			description: COPY.data.description,
			markdown: dataMarkdown(),
		},
		{
			slug: "data/run-notes",
			path: "/data/run-notes/",
			title: COPY.runNotes.title,
			description: COPY.runNotes.description,
			markdown: runNotesMarkdown(),
		},
	];
	for (const model of snapshot.models) {
		docs.push({
			slug: `models/${model.slug}`,
			path: `/models/${model.slug}/`,
			title: model.display_name,
			description: `${model.display_name} on LegalForecastBench: micro Brier ${model.micro_brier.toFixed(4)} across ${snapshot.cohort.unit_count} units.`,
			markdown: modelMarkdown(model.slug),
		});
	}
	for (const entry of findings) {
		const date = entry.data.date.toISOString().slice(0, 10);
		const body = mdxToMarkdown(findingSource(entry.id));
		docs.push({
			slug: `findings/${entry.id}`,
			path: `/findings/${entry.id}/`,
			title: entry.data.title,
			description: entry.data.summary,
			markdown: [
				header(entry.data.title, entry.data.summary, `/findings/${entry.id}/`),
				`Author: ${entry.data.author}`,
				`Published: ${date}`,
				"",
				body,
			].join("\n"),
		});
	}
	return docs;
}
