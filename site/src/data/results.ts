import { applyComparison } from "./comparison.js";
import { extendSnapshot } from "./extend-snapshot.js";
import { applyReceiptCosts } from "./receipt-costs.js";
import { recentResults } from "./recent-results.js";
import { parseSnapshot } from "./snapshot.js";
import beta from "./snapshots/beta-2026-09-18.json" with { type: "json" };

export const historicalSnapshot = parseSnapshot(structuredClone(beta));
/** Historical beta rows plus validated native exports of later agentic runs. */
export const snapshot = applyComparison(
	applyReceiptCosts(
		extendSnapshot(historicalSnapshot, recentResults),
		recentResults.map(({ source }) => source),
	),
);

/**
 * Older configurations kept as references: they have model pages and appear in
 * experiments, but are not ranked or charted with current models.
 */
export const REFERENCE_SLUGS: ReadonlySet<string> = new Set(["gpt-4-1"]);

/** The ranked comparison: every configuration except references. */
export const primarySnapshot = {
	...snapshot,
	models: snapshot.models.filter((model) => !REFERENCE_SLUGS.has(model.slug)),
	significant_pairs: snapshot.significant_pairs.filter(
		(pair) =>
			!REFERENCE_SLUGS.has(pair.better) && !REFERENCE_SLUGS.has(pair.worse),
	),
};
