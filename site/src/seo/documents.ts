import { REPO } from "../data/author.js";
import { paperHeadline } from "../data/headline.js";
import { formatPercent } from "../data/metrics.js";
import { PAPER } from "../data/paper.js";
import { PAPER_PROSE } from "../data/paper-prose.js";
import {
	primarySnapshot,
	releaseDescription,
	snapshot,
} from "../data/results.js";
import type { AgentDocument } from "./agent-document.js";
import { COPY, HOME_INTRO } from "./copy.js";
import { absoluteUrl } from "./identity.js";

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
	return [
		header(COPY.home.title, COPY.home.description, "/"),
		HOME_INTRO,
		"",
		"## Results",
		"",
		...(paperHeadline ? [paperHeadline, ""] : []),
		...leaderboardLines(),
		"## Why judicial outcomes (from the working paper)",
		"",
		PAPER_PROSE.groundTruth,
		"",
		PAPER_PROSE.whyMotions,
		"",
		PAPER_PROSE.nextSteps,
		"",
	].join("\n");
}

function leaderboardLines(): string[] {
	const ranked = [...primarySnapshot.models].sort(
		(a, b) => a.micro_brier - b.micro_brier,
	);
	const n = snapshot.cohort.unit_count;
	const lines = [
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
	return lines;
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
		`Ranked comparison: ${absoluteUrl("/#leaderboard")}`,
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

function dataMarkdown(): string {
	const { provenance } = snapshot;
	return [
		header(COPY.data.title, COPY.data.description, "/data/"),
		PAPER_PROSE.access,
		"",
		releaseDescription(),
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

export function agentDocuments(): AgentDocument[] {
	const docs: AgentDocument[] = [
		{
			slug: "home",
			path: "/",
			title: COPY.home.title,
			description: COPY.home.description,
			markdown: homeMarkdown(),
		},
		{
			slug: "paper",
			path: "/paper/",
			title: PAPER.title,
			description: COPY.paper.description,
			markdown: paperMarkdown(),
		},
		{
			slug: "data",
			path: "/data/",
			title: COPY.data.title,
			description: COPY.data.description,
			markdown: dataMarkdown(),
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
	return docs;
}
