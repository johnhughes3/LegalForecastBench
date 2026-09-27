import { Ajv2020 } from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import schema from "./snapshots/snapshot.schema.json" with { type: "json" };

export type Metric = "micro_brier" | "equal_case_brier" | "accuracy";
export type Eligibility = "eligible" | "qualified" | "unknown";

export interface SnapshotModel {
	slug: string;
	display_name: string;
	provider: string;
	model_key: string;
	access: string;
	reasoning: string;
	release_date: string;
	training_cutoff: string | null;
	eligibility: Eligibility;
	eligibility_reason: string;
	github_run_id: string;
	unit_data_retained: boolean;
	micro_brier: number;
	equal_case_brier: number;
	correct: number;
	high_confidence: {
		count: number;
		wrong: number;
		mean_confidence: number | null;
	};
	cost: {
		usd: number | null;
		basis: "standard_rate" | "estimated" | "unavailable";
		note: string | null;
	};
}

export interface ResultsSnapshot {
	snapshot_id: string;
	title: string;
	status: "beta" | "official";
	as_of: string;
	provenance: {
		release: string;
		release_digest: string;
		method: string;
		unit_level_note: string;
	};
	cohort: {
		case_count: number;
		unit_count: number;
		dismissed_unit_count: number;
		decision_window: { start: string; end: string };
		constant_forecast_micro_brier: number;
		majority_class_accuracy: number;
		bootstrap: {
			method: string;
			replicates: number;
			correction: string;
			caveat: string;
		};
	};
	significant_pairs: { better: string; worse: string; metric: Metric }[];
	models: SnapshotModel[];
}

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validate = ajv.compile<ResultsSnapshot>(schema);

/**
 * Validate a hand-transcribed snapshot, then check that its internal
 * references and counts agree, because nothing upstream generated it.
 */
export function parseSnapshot(value: unknown): ResultsSnapshot {
	if (!validate(value)) {
		throw new Error(
			`Invalid results snapshot: ${ajv.errorsText(validate.errors, { separator: "; " })}`,
		);
	}
	const slugs = new Set(value.models.map((model) => model.slug));
	if (slugs.size !== value.models.length) {
		throw new Error("Invalid results snapshot: duplicate model slug");
	}
	for (const pair of value.significant_pairs) {
		if (!slugs.has(pair.better) || !slugs.has(pair.worse)) {
			throw new Error(
				`Invalid results snapshot: unknown model in significant pair ${pair.better}/${pair.worse}`,
			);
		}
	}
	const { unit_count, dismissed_unit_count } = value.cohort;
	if (dismissed_unit_count > unit_count) {
		throw new Error(
			"Invalid results snapshot: more dismissed units than units",
		);
	}
	for (const model of value.models) {
		if (
			model.correct > unit_count ||
			model.high_confidence.count > unit_count
		) {
			throw new Error(
				`Invalid results snapshot: ${model.slug} counts exceed the cohort`,
			);
		}
		if (model.high_confidence.wrong > model.high_confidence.count) {
			throw new Error(
				`Invalid results snapshot: ${model.slug} has more high-confidence misses than predictions`,
			);
		}
	}
	return value;
}
