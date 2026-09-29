import table from "../../../legalforecast/data/model_cutoffs.json" with {
	type: "json",
};
import type {
	Eligibility,
	ResultsSnapshot,
	SnapshotModel,
} from "./snapshot.js";

/**
 * Comparison eligibility from the maintained cutoff table that the Python
 * exporter also uses (legalforecast/data/model_cutoffs.json). Owner rule,
 * 2026-09-28: eligible when the provider-reported training-data or knowledge
 *  cutoff falls before the earliest scored decision; a month counts as its
 * first day, because same-day ingestion of a new decision is implausible
 * (owner decision, 2026-09-28).
 */
export interface CutoffEntry {
	slug: string;
	model_ids: string[];
	cutoff: string | null;
	kind: "training" | "knowledge" | null;
	note?: string;
}

export const cutoffTable: CutoffEntry[] = table.models as CutoffEntry[];

const MONTHS = [
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
];

/** The latest date a cutoff could mean, as an ISO string. */
export function lastDay(cutoff: string): string {
	const [year, month, day] = cutoff.split("-").map(Number);
	if (!year || !month) throw new Error(`Unsupported cutoff ${cutoff}`);
	if (day) return cutoff;
	const last = new Date(Date.UTC(year, month, 0)).getUTCDate();
	return `${cutoff}-${String(last).padStart(2, "0")}`;
}

export function formatCutoff(cutoff: string): string {
	const [year, month, day] = cutoff.split("-").map(Number);
	const name = MONTHS[(month ?? 1) - 1];
	return day ? `${name} ${day}, ${year}` : `${name} ${year}`;
}

const formatIso = (iso: string) => formatCutoff(iso);

export function assess(
	entry: CutoffEntry,
	firstDecision: string,
): {
	eligibility: Eligibility;
	reason: string;
	training_cutoff: string | null;
} {
	const note = entry.note ? ` ${entry.note}` : "";
	if (!entry.cutoff) {
		return {
			eligibility: "qualified",
			reason: `The provider has not published a training or knowledge cutoff.${note}`,
			training_cutoff: null,
		};
	}
	const kind = entry.kind === "training" ? "training-data" : "knowledge";
	const label = formatCutoff(entry.cutoff);
	const training_cutoff = `${label} (${kind} cutoff)`;
	// A month-only cutoff is compared as the first day of its month: ingesting a
	// decision on the day it issued is implausible (owner decision, 2026-09-28).
	const monthOnly = entry.cutoff.length === 7;
	const compared = monthOnly ? `${entry.cutoff}-01` : entry.cutoff;
	const precedes = compared < firstDecision;
	if (precedes) {
		return {
			eligibility: "eligible",
			reason:
				monthOnly && entry.cutoff === firstDecision.slice(0, 7)
					? `The reported ${kind} cutoff (${label}) is in the month of the first scored decision (${formatIso(firstDecision)}). It is treated as preceding that decision, because a ruling is very unlikely to enter training data the day it issues.${note}`
					: `The reported ${kind} cutoff (${label}) predates the first scored decision on ${formatIso(firstDecision)}.${note}`,
			training_cutoff,
		};
	}
	return {
		eligibility: "qualified",
		reason: `The reported ${kind} cutoff (${label}) falls on or after the first scored decision on ${formatIso(firstDecision)}.${note}`,
		training_cutoff,
	};
}

/** Apply the cutoff table to every model; every displayed model must be listed. */
export function applyCutoffs(snapshot: ResultsSnapshot): ResultsSnapshot {
	const first = snapshot.cohort.decision_window.start;
	const models = snapshot.models.map((model): SnapshotModel => {
		const entry = cutoffTable.find((e) => e.slug === model.slug);
		if (!entry)
			throw new Error(`No cutoff evidence recorded for ${model.slug}`);
		const { eligibility, reason, training_cutoff } = assess(entry, first);
		return {
			...model,
			eligibility,
			eligibility_reason: reason,
			training_cutoff,
		};
	});
	return { ...snapshot, models };
}
