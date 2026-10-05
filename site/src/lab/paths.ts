/** Site paths and repository links for the LAB explorer. Pure, so the browser can import it. */
import type { RunKey } from "./types.js";

export const AUDIT_PATH = "docs/harvey-lab-audit/litigation-dispute-resolution";

/** Directory names under model-runs/<task>/. */
export const RUN_DIRECTORY: Record<RunKey, string> = {
	luna: "gpt6luna-xhigh",
	opus: "opus55-low",
};

const REPO_BLOB = "https://github.com/johnhughes3/LegalForecastBench/blob/main";

export const LAB_ROOT = "/lab/";
export const labRunsPath = `${LAB_ROOT}runs/`;
export const labTaskPath = (task: string): string =>
	`${LAB_ROOT}tasks/${task}/`;
export const labCriterionPath = (task: string, criterion: string): string =>
	`${labTaskPath(task)}#${criterion.toLowerCase()}`;
export const labReviewPath = (number: number): string =>
	`${LAB_ROOT}review/${number}/`;
export const labDeliverablePath = (
	task: string,
	run: RunKey,
	name: string,
): string => `${LAB_ROOT}deliverables/${task}/${RUN_DIRECTORY[run]}/${name}/`;

/** The original deliverable (a .docx or .xlsx) in the repository. */
export const originalDeliverableUrl = (
	task: string,
	run: RunKey,
	name: string,
): string =>
	`${REPO_BLOB}/${AUDIT_PATH}/model-runs/${task}/${RUN_DIRECTORY[run]}/output/${name}`;

/** One judge's raw score file in the repository. */
export const scoreFileUrl = (
	task: string,
	run: RunKey,
	judge: "claude-sonnet-4-6" | "gpt-5.5",
): string =>
	`${REPO_BLOB}/${AUDIT_PATH}/model-runs/${task}/${RUN_DIRECTORY[run]}/scores_${judge}.json`;

export const taskAuditReportUrl = (
	task: string,
	report: "gpt-6-sol-audit.md" | "claude-opus-5-5-audit.md",
): string => `${REPO_BLOB}/${AUDIT_PATH}/tasks/${task}/${report}`;

export const REVIEW_PROTOCOL_URL = `${REPO_BLOB}/${AUDIT_PATH}/human-review/README.md`;
export const REVIEW_WORKSHEET_URL = `${REPO_BLOB}/${AUDIT_PATH}/human-review/worksheet.md`;
export const AUDIT_README_URL = `${REPO_BLOB}/${AUDIT_PATH}/README.md`;
