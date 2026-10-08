/**
 * The abstract's headline sentence, when it still describes the published
 * results. The checked-in release must match it, or the build fails. A
 * refreshed cohort (after case withdrawals) is a different release, so the
 * sentence is omitted rather than shown beside numbers it does not describe.
 */
import { refreshedDataDirectory } from "./dataset-input.js";
import { PAPER_PROSE } from "./paper-prose.js";
import { primarySnapshot } from "./results.js";

function staleFacts(sentence: string): string[] {
	const { cohort, models } = primarySnapshot;
	const [leader] = [...models].sort((a, b) => a.micro_brier - b.micro_brier);
	if (!leader) return ["no ranked models"];
	const n = cohort.unit_count;
	return [
		`${cohort.case_count} cases`,
		`${n} scored`,
		leader.display_name,
		`(${leader.micro_brier.toFixed(3)})`,
		`(${((100 * leader.correct) / n).toFixed(1)}%)`,
		`${models.length} frontier models`,
	].filter((fact) => !sentence.includes(fact));
}

const stale = staleFacts(PAPER_PROSE.headline);
if (stale.length > 0 && !refreshedDataDirectory) {
	throw new Error(
		`The abstract's headline sentence no longer matches the results (${stale.join("; ")}). Update the paper or the data before publishing.`,
	);
}

export const paperHeadline: string | null =
	stale.length === 0 ? PAPER_PROSE.headline : null;
