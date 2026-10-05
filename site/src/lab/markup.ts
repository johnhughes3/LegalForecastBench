/**
 * HTML-string helpers shared by Astro pages (via `set:html`) and the browser
 * scripts, so a chip or a criterion body is drawn by one piece of code
 * wherever it appears. Every dynamic value is escaped here; callers pass plain
 * text, never markup. Styles live in styles/lab.css.
 */
import type { CriterionDetail } from "./index-format.js";
import { GRADE_SLOTS } from "./index-format.js";
import {
	BUCKET_LABEL,
	JUDGE_LABEL,
	RUN_LABEL,
	RUN_SHORT,
	STATUS_LABEL,
} from "./labels.js";
import { labDeliverablePath, scoreFileUrl } from "./paths.js";
import type {
	AiAudit,
	AiStatus,
	JudgeKey,
	RubricVerdict,
	RunKey,
	Verdict,
} from "./types.js";
import { upstreamTaskUrl } from "./upstream.js";

export function escapeHtml(text: string): string {
	return text
		.replaceAll("&", "&amp;")
		.replaceAll("<", "&lt;")
		.replaceAll(">", "&gt;")
		.replaceAll('"', "&quot;");
}

const JUDGE_LETTER: Record<JudgeKey, string> = { sonnet: "S", gpt: "G" };

function gradeCell(judge: JudgeKey, verdict: Verdict): string {
	const pass = verdict === "pass";
	return `<span class="lab-g ${pass ? "lab-g-pass" : "lab-g-fail"}" role="img" aria-label="${JUDGE_LABEL[judge]} ${verdict}"><i>${JUDGE_LETTER[judge]}</i>${pass ? "✓" : "✗"}</span>`;
}

/** One run's two native grades, e.g. "Luna S✓ G✗". */
export function gradePairHtml(
	run: RunKey,
	sonnet: Verdict,
	gpt: Verdict,
): string {
	return `<span class="lab-pair" role="group" aria-label="${escapeHtml(RUN_LABEL[run])}"><b>${RUN_SHORT[run]}</b>${gradeCell("sonnet", sonnet)}${gradeCell("gpt", gpt)}</span>`;
}

/** An AI audit model's status, labeled as AI so it is never read as a human finding. */
export function aiStatusHtml(
	model: "Sol" | "Opus",
	status: AiStatus | null,
): string {
	if (status === null) return "";
	const tone =
		status === "problematic" || status === "arguable" ? status : "unverified";
	return `<span class="lab-chip lab-chip-${tone}"><i>AI ${model}</i>${STATUS_LABEL[status]}</span>`;
}

const REVIEW_CLASS: Record<RubricVerdict, string> = {
	Defective: "lab-rev-defective",
	Arguable: "lab-rev-arguable",
	"Not defective": "lab-rev-not-defective",
	Unresolved: "lab-rev-unresolved",
};

/** The reviewer's rubric verdict. Visibly human: it names the reviewer, never "AI". */
export function reviewBadgeHtml(
	verdict: RubricVerdict,
	number?: number,
): string {
	const prefix = number === undefined ? "Reviewer" : `Reviewer #${number}`;
	return `<span class="lab-rev ${REVIEW_CLASS[verdict]}"><b>${prefix}:</b>${verdict}</span>`;
}

function list(items: readonly string[]): string {
	return `<ul>${items.map((text) => `<li>${escapeHtml(text)}</li>`).join("")}</ul>`;
}

/** The AI audit block: statuses, agreement group, and each model's findings. */
export function findingsHtml(ai: AiAudit, level: "h3" | "h4" = "h3"): string {
	const group =
		ai.bucket === null
			? "Not flagged in the final position of either model"
			: BUCKET_LABEL[ai.bucket];
	const blind =
		ai.opusBlind && ai.opusBlind !== ai.opus
			? ` <span class="lab-links">Opus's blind pass (before it saw Sol's work): ${escapeHtml(ai.opusBlind)}</span>`
			: "";
	const parts = [
		`<${level} class="lab-h">AI audit findings <small>(AI-generated, unverified)</small></${level}>`,
		`<p><span class="lab-chip lab-chip-unverified">${escapeHtml(group)}</span></p>`,
		`<p class="lab-tags">${aiStatusHtml("Sol", ai.sol)}${aiStatusHtml("Opus", ai.opus)}${blind}</p>`,
	];
	if (ai.solFindings.length > 0)
		parts.push(`<p class="who">GPT-6 Sol</p>${list(ai.solFindings)}`);
	if (ai.opusFindings.length > 0)
		parts.push(`<p class="who">Claude Opus 5.5</p>${list(ai.opusFindings)}`);
	if (ai.opusOnSol.length > 0)
		parts.push(
			`<p class="who">Claude Opus 5.5's ruling on GPT-6 Sol's finding</p>${list(ai.opusOnSol)}`,
		);
	if (
		ai.bucket === null &&
		ai.solFindings.length + ai.opusFindings.length === 0
	)
		parts.push("<p>No audit finding recorded for this criterion.</p>");
	return `<div class="lab-findings">${parts.join("")}</div>`;
}

/** The four native grades with each judge's reasoning, grouped by run. */
export function gradeCardsHtml(task: string, detail: CriterionDetail): string {
	const judgeFile = { sonnet: "claude-sonnet-4-6", gpt: "gpt-5.5" } as const;
	const cards = GRADE_SLOTS.map(({ run, judge }, slot) => {
		const pass = detail.verdicts[slot] === "pass";
		return `<div class="lab-grade-card"><header><strong>${escapeHtml(RUN_LABEL[run])}</strong><span>· ${JUDGE_LABEL[judge]} (AI judge)</span><span class="lab-g ${pass ? "lab-g-pass" : "lab-g-fail"}">${pass ? "✓ Pass" : "✗ Fail"}</span></header><p>${escapeHtml(detail.reasoning[slot] ?? "")}</p><p class="lab-links"><a href="${escapeHtml(scoreFileUrl(task, run, judgeFile[judge]))}">score file</a></p></div>`;
	});
	const links = (["luna", "opus"] as const)
		.flatMap((run) =>
			detail.deliverables[run].map(
				(name) =>
					`<a href="${escapeHtml(labDeliverablePath(task, run, name))}">${escapeHtml(RUN_SHORT[run])}: ${escapeHtml(name)}</a>`,
			),
		)
		.join(" · ");
	return `<div class="lab-grade-grid">${cards.join("")}</div>${links ? `<p class="lab-links mt-2">Graded against: ${links}</p>` : ""}`;
}

/** Everything inside an opened criterion except the reviewer's block. */
export function criterionBodyHtml(
	task: string,
	detail: CriterionDetail,
): string {
	const rubricLink = upstreamTaskUrl(task, detail.line ?? undefined);
	const hasFindings =
		detail.ai.bucket !== null ||
		detail.ai.solFindings.length > 0 ||
		detail.ai.opusFindings.length > 0;
	return [
		`<div><h3 class="lab-h">Rubric criterion <small>(Harvey's text)</small></h3><p class="lab-rubric">${escapeHtml(detail.rubric)}</p><p class="lab-links mt-1"><a href="${escapeHtml(rubricLink)}">View in task.json</a></p></div>`,
		hasFindings ? findingsHtml(detail.ai, "h3") : "",
		`<div><h3 class="lab-h">How the runs were graded <small>(AI judges, unverified)</small></h3>${gradeCardsHtml(task, detail)}</div>`,
	].join("");
}
