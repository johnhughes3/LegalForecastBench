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
