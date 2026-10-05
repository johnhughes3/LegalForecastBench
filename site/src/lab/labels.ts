/** Display names and short phrases for the LAB explorer. */
import type { AiStatus, Bucket, JudgeKey, RunKey } from "./types.js";

export const RUN_LABEL: Record<RunKey, string> = {
	luna: "GPT-6 Luna (xhigh)",
	opus: "Claude Opus 5.5 (low)",
};
export const RUN_SHORT: Record<RunKey, string> = {
	luna: "Luna",
	opus: "Opus",
};
export const JUDGE_LABEL: Record<JudgeKey, string> = {
	sonnet: "Sonnet 4.6",
	gpt: "GPT-5.5",
};

export const STATUS_LABEL: Record<AiStatus, string> = {
	problematic: "problematic",
	arguable: "arguable",
	unverified: "unverified",
	qualified_check: "qualified check",
};

export const BUCKET_LABEL: Record<Bucket, string> = {
	both_problematic: "Both models: problematic",
	both_arguable: "Both models: arguable",
	split: "Both flagged, different strength",
	sol_only: "GPT-6 Sol only",
	opus_only: "Claude Opus 5.5 only",
};

export const AI_NOTICE =
	"AI-generated and unverified. The audit findings and the pass/fail grades on this page come from AI models, not from a human. The only human judgments are the reviewer's verdicts on the 25 hand-audited criteria.";
