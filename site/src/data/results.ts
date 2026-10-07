import { applyComparison } from "./comparison.js";
import { datasetJson, refreshedDataDirectory } from "./dataset-input.js";
import { applyCutoffs } from "./eligibility.js";
import { extendSnapshot } from "./extend-snapshot.js";
import { applyReceiptCosts } from "./receipt-costs.js";
import { recentResults } from "./recent-results.js";
import { parseSnapshot } from "./snapshot.js";
import beta from "./snapshots/beta-2026-09-18.json" with { type: "json" };

export const historicalSnapshot = parseSnapshot(structuredClone(beta));
/** Historical beta rows plus validated native exports of later agentic runs. */
const defaultSnapshot = () =>
	applyCutoffs(
		applyComparison(
			applyReceiptCosts(
				extendSnapshot(historicalSnapshot, recentResults),
				recentResults.map(({ source }) => source),
				undefined,
				recentResults,
			),
		),
	);

/**
 * Older configurations kept as references: they have model pages and appear in
 * experiments, but are not ranked or charted with current models.
 */
export const snapshot = refreshedDataDirectory
	? parseSnapshot(datasetJson<unknown>("current.json", null))
	: defaultSnapshot();

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

/**
 * One sentence on what the release scores. The data page's JSON-LD and its
 * markdown copy share it, so the count cannot differ between them. References
 * are named apart from the ranked configurations the paper counts.
 */
export function releaseDescription(): string {
	const { cohort } = snapshot;
	const references = snapshot.models
		.filter((model) => REFERENCE_SLUGS.has(model.slug))
		.map((model) => model.display_name);
	const reference =
		references.length > 0
			? `, plus ${references.join(", ")} as a historical reference for non-thinking models,`
			: "";
	return `Forecasts by ${primarySnapshot.models.length} ranked AI model configurations${reference} of whether each challenged claim in ${cohort.case_count} federal motions to dismiss would be fully dismissed, scored against the actual rulings (${cohort.unit_count} claim-defendant units).`;
}

/** The results release every page is computed from. */
export const CURRENT_RELEASE = `Cycle 1 beta · ${new Date(
	`${snapshot.as_of}T00:00:00Z`,
).toLocaleDateString("en-US", {
	month: "long",
	day: "numeric",
	year: "numeric",
	timeZone: "UTC",
})}`;
