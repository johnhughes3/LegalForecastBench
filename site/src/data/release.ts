/**
 * The published results release, as labeled on the site.
 *
 * The benchmark is versioned by cycle, not by a running number. Each cycle
 * scores a new, fixed cohort of cases, so a later cycle is a different
 * benchmark rather than an improved edition of this one, and its scores are
 * not a time series. The machine identity of a release is the corpus release
 * id in the snapshot's provenance; the human label pairs the cycle that id
 * names with the date the results were published, which is `date-released`
 * in CITATION.cff. Nothing else on the site states the cycle or the date.
 */
import { formatLongDate } from "./metrics.js";
import { SOFTWARE_CITATION } from "./paper.js";
import { snapshot } from "./results.js";
import type { ResultsSnapshot } from "./snapshot.js";

/** The cycle number a corpus release id names, e.g. `cycle-1-91-...` → 1. */
export function cycleOf(release: string): number {
	const match = /^cycle-(\d+)-/.exec(release);
	if (!match) {
		throw new Error(`Release id "${release}" does not name a cycle.`);
	}
	return Number(match[1]);
}

/** "Cycle 1" or, while the results are still beta, "Cycle 1 beta". */
export function cycleLabel(
	release: string,
	status: ResultsSnapshot["status"],
): string {
	const cycle = `Cycle ${cycleOf(release)}`;
	return status === "beta" ? `${cycle} beta` : cycle;
}

export interface Release {
	/** The corpus release id, the machine identity published as the dataset version. */
	id: string;
	cycle: number;
	/** "Cycle 1" with no status suffix, for prose that names the cohort. */
	cycleName: string;
	/** ISO date the results were published. */
	publishedOn: string;
	/** The hero eyebrow: "Cycle 1 beta · October 13, 2026". */
	label: string;
}

export function describeRelease(
	id: string,
	status: ResultsSnapshot["status"],
	publishedOn: string,
): Release {
	return {
		id,
		cycle: cycleOf(id),
		cycleName: `Cycle ${cycleOf(id)}`,
		publishedOn,
		label: `${cycleLabel(id, status)} · ${formatLongDate(publishedOn)}`,
	};
}

export const RELEASE: Release = describeRelease(
	snapshot.provenance.release,
	snapshot.status,
	SOFTWARE_CITATION.date,
);
