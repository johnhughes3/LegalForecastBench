/**
 * Build-time loader for the LAB explorer.
 *
 * Joins, per task: the vendored upstream task.json (instructions and every
 * rubric criterion), the Claude Opus 5.5 audit JSON (line numbers), the
 * comparison rows (both audit models' findings), four native score files, and
 * the reviewer's worksheet. Nothing here runs in the browser.
 *
 * Failure policy: the joins are checked rather than trusted. A task whose
 * criteria disagree across sources throws, so a data refresh that drifts fails
 * the build instead of publishing misaligned grades.
 */
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { repositoryRoot } from "../data/manuscript.js";
import { JUDGES, RUNS } from "./flags.js";
import { AUDIT_PATH, RUN_DIRECTORY } from "./paths.js";
import type {
	AiAudit,
	AiStatus,
	Bucket,
	Criterion,
	Grade,
	Grades,
	JudgeKey,
	LabData,
	RunKey,
	RunSummary,
	Task,
	TaskDocument,
	Verdict,
} from "./types.js";
import { upstreamDocumentUrl } from "./upstream.js";
import { parseWorksheet } from "./worksheet.js";

const JUDGE_FILE: Record<JudgeKey, string> = {
	sonnet: "claude-sonnet-4-6",
	gpt: "gpt-5.5",
};

type UpstreamTask = {
	title: string;
	work_type: string;
	tags: string[];
	instructions: string;
	criteria: {
		id: string;
		title: string;
		deliverables: string[];
		match_criteria: string;
	}[];
};
type OpusAudit = {
	criteria_total: number;
	criterion_lines: Record<string, number>;
};
type ComparisonRow = {
	task: string;
	criterion: string;
	gpt_6_sol: AiStatus | null;
	claude_opus_5_5: AiStatus | null;
	claude_opus_5_5_blind: AiStatus | null;
	bucket: Bucket | null;
	sol_findings: string[];
	opus_findings: string[];
	opus_on_sol: string[];
};
type ScoreFile = {
	n_passed: number;
	n_criteria: number;
	all_pass: boolean;
	criteria_results: { id: string; verdict: Verdict; reasoning: string }[];
};

const root = repositoryRoot();
const auditDir = resolve(root, AUDIT_PATH);

function readJson<T>(path: string): T {
	return JSON.parse(readFileSync(path, "utf8")) as T;
}

/** Native deliverable file name for a rendered `output/*.md` file. */
export function deliverableName(markdownFile: string): string {
	return markdownFile.replace(/\.(docx|xlsx)\.md$/, ".$1");
}

export const deliverableId = (
	task: string,
	run: RunKey,
	name: string,
): string => `${task}/${RUN_DIRECTORY[run]}/${name}`;

function documentsFromReadme(task: string): TaskDocument[] {
	const readme = readFileSync(
		resolve(auditDir, "tasks", task, "README.md"),
		"utf8",
	);
	const section = /## Pinned upstream sources\n([\s\S]*?)\n(?:<!--|## )/.exec(
		readme,
	)?.[1];
	if (!section) throw new Error(`${task}: pinned source list not found.`);
	return [...section.matchAll(/^- \[([^\]]+)\]\(/gm)]
		.map((match) => match[1] ?? "")
		.filter((name) => name !== "" && !name.includes("task.json"))
		.map((name) => ({ name, url: upstreamDocumentUrl(task, name) }));
}

function loadScores(task: string, run: RunKey, judge: JudgeKey): ScoreFile {
	return readJson<ScoreFile>(
		resolve(
			auditDir,
			"model-runs",
			task,
			RUN_DIRECTORY[run],
			`scores_${JUDGE_FILE[judge]}.json`,
		),
	);
}

function buildTask(
	slug: string,
	rows: ReadonlyMap<string, ComparisonRow>,
	reviewByKey: ReadonlyMap<string, number>,
): Task {
	const upstream = readJson<UpstreamTask>(
		resolve(root, "site/src/data/lab/upstream", `${slug}.json`),
	);
	const audit = readJson<OpusAudit>(
		resolve(auditDir, "tasks", slug, "claude-opus-5-5-audit.json"),
	);
	if (upstream.criteria.length !== audit.criteria_total)
		throw new Error(
			`${slug}: upstream has ${upstream.criteria.length} criteria, audit says ${audit.criteria_total}.`,
		);

	const scores = {
		luna: {
			sonnet: loadScores(slug, "luna", "sonnet"),
			gpt: loadScores(slug, "luna", "gpt"),
		},
		opus: {
			sonnet: loadScores(slug, "opus", "sonnet"),
			gpt: loadScores(slug, "opus", "gpt"),
		},
	} satisfies Record<RunKey, Record<JudgeKey, ScoreFile>>;

	// Verify each score file against the rubric and against its own summary, so
	// a refreshed or truncated file fails the build rather than shipping grades
	// that do not belong to this rubric.
	for (const run of RUNS) {
		for (const judge of JUDGES) {
			const file = scores[run][judge];
			const where = `${slug} ${run}/${judge}`;
			const counted = file.criteria_results.filter(
				(result) => result.verdict === "pass",
			).length;
			if (
				file.criteria_results.length !== upstream.criteria.length ||
				file.n_criteria !== upstream.criteria.length
			)
				throw new Error(
					`${where}: ${file.criteria_results.length} results, n_criteria ${file.n_criteria}, rubric ${upstream.criteria.length}.`,
				);
			if (file.n_passed !== counted)
				throw new Error(
					`${where}: n_passed ${file.n_passed}, counted ${counted}.`,
				);
			if (file.all_pass !== (counted === file.criteria_results.length))
				throw new Error(`${where}: all_pass disagrees with the verdicts.`);
		}
	}

	const criteria = upstream.criteria.map((source, index): Criterion => {
		const grades = {} as Grades;
		for (const run of RUNS) {
			const byJudge = {} as Record<JudgeKey, Grade>;
			for (const judge of JUDGES) {
				const result = scores[run][judge].criteria_results[index];
				if (result?.id !== source.id)
					throw new Error(
						`${slug}: ${run}/${judge} misaligned at ${source.id}.`,
					);
				byJudge[judge] = {
					verdict: result.verdict,
					reasoning: result.reasoning,
				};
			}
			grades[run] = byJudge;
		}
		const row = rows.get(`${slug}/${source.id}`);
		const ai: AiAudit = {
			sol: row?.gpt_6_sol ?? null,
			opus: row?.claude_opus_5_5 ?? null,
			opusBlind: row?.claude_opus_5_5_blind ?? null,
			bucket: row?.bucket ?? null,
			solFindings: row?.sol_findings ?? [],
			opusFindings: row?.opus_findings ?? [],
			opusOnSol: row?.opus_on_sol ?? [],
		};
		return {
			id: source.id,
			number: Number(source.id.slice(2)),
			title: source.title,
			rubric: source.match_criteria,
			line: audit.criterion_lines[source.id] ?? null,
			deliverables: source.deliverables,
			ai,
			grades,
			review: reviewByKey.get(`${slug}/${source.id}`) ?? null,
		};
	});

	const summarize = (run: RunKey): RunSummary => {
		const judges = {} as RunSummary["judges"];
		for (const judge of JUDGES) {
			const file = scores[run][judge];
			judges[judge] = {
				passed: file.n_passed,
				total: file.n_criteria,
				allPass: file.all_pass,
			};
		}
		const outputDir = resolve(
			auditDir,
			"model-runs",
			slug,
			RUN_DIRECTORY[run],
			"output",
		);
		const deliverables = readdirSync(outputDir)
			.filter((file) => file.endsWith(".md"))
			.sort()
			.map(deliverableName);
		return { judges, deliverables };
	};

	return {
		slug,
		title: upstream.title,
		workType: upstream.work_type,
		tags: upstream.tags,
		instructions: upstream.instructions,
		documents: documentsFromReadme(slug),
		criteria,
		runs: { luna: summarize("luna"), opus: summarize("opus") },
	};
}

let cached: LabData | undefined;

export function loadLab(): LabData {
	if (cached) return cached;
	const review = parseWorksheet(
		readFileSync(resolve(auditDir, "human-review/worksheet.md"), "utf8"),
	);
	const reviewByKey = new Map(
		review.map((item) => [`${item.task}/${item.criterion}`, item.number]),
	);
	const comparison = readJson<{ rows: ComparisonRow[] }>(
		resolve(auditDir, "comparison.json"),
	);
	const rows = new Map(
		comparison.rows.map((row) => [`${row.task}/${row.criterion}`, row]),
	);
	const slugs = readdirSync(resolve(auditDir, "tasks"), { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
	const tasks = slugs.map((slug) => buildTask(slug, rows, reviewByKey));

	for (const item of review) {
		const found = tasks
			.find((task) => task.slug === item.task)
			?.criteria.some((criterion) => criterion.id === item.criterion);
		if (!found)
			throw new Error(`Review item ${item.number} names a missing criterion.`);
	}
	const flaggedTotal = tasks.reduce(
		(sum, task) =>
			sum + task.criteria.filter((c) => c.ai.bucket !== null).length,
		0,
	);
	cached = { tasks, review, flaggedTotal };
	return cached;
}
