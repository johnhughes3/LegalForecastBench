import provenance from "../../public/data/summary-comparison/catalog.json";
import type { SiteCalibrationBin, SiteExport } from "../generated/site-export";
import gpt41 from "./exports/gpt-4-1.json";
import lunaHigh from "./exports/gpt-5-6-luna-summaries-high.json";
import lunaNone from "./exports/gpt-6-luna-summaries-none.json";
import jev from "./exports/jev-luna-summaries.json";
import { publicUnitCensus } from "./extend-snapshot";
import { meanForecast, rankAuc } from "./metrics";
import { parseSiteExport } from "./site-export";

export interface SupplementaryRow {
	slug: string;
	display_name: string;
	input_label: string;
	reasoning_label: string;
	role: "comparison" | "reasoning-reference" | "full-record-reference";
	micro_brier: number;
	equal_case_brier: number;
	correct: number;
	unit_count: number;
	case_count: number;
	forecast_run: string;
	source_url: string;
	auc: number;
	mean_forecast: number;
	calibration: SiteCalibrationBin[];
	/** Registry-rate estimate for the successful workload; null when not recorded here. */
	inference_usd: number | null;
	preparation_usd: number | null;
}

export interface SummarySource {
	slug: string;
	forecast_run: string;
	model_key: string;
	summary_cache_sha256: string;
	run_identity_sha256: string;
	model_registry_sha256: string;
	summary_preparation_estimated_usd: number;
	successful_inference_estimated_usd: number;
}

export interface SummaryComparison {
	source: SummarySource;
	data: SiteExport;
}

const exports = [jev, lunaNone, lunaHigh].map(parseSiteExport);
export const summaryComparisons: SummaryComparison[] = provenance.map(
	(item) => {
		const source = { ...item, forecast_run: item.forecast_run_id };
		const data = exports.find(
			(item) => item.source.run_identity_sha256 === source.run_identity_sha256,
		);
		if (!data) throw new Error(`Missing summary export for ${source.slug}`);
		return { source, data };
	},
);

/** Keep summary conditions outside the agentic snapshot and match the scored cohort. */
export function buildSupplementaryRows(
	comparisons: SummaryComparison[],
	reference: SiteExport,
): SupplementaryRow[] {
	const referenceRow = reference.results[0];
	if (!referenceRow || reference.results.length !== 1)
		throw new Error("Expected one full-record reference");
	const census = publicUnitCensus(referenceRow.units);
	const cache = comparisons[0]?.source.summary_cache_sha256;
	const slugs = new Set<string>();
	const rows = comparisons.map(({ source, data }): SupplementaryRow => {
		const row = data.results[0];
		if (slugs.has(source.slug)) throw new Error("Duplicate summary condition");
		slugs.add(source.slug);
		if (
			!row ||
			data.results.length !== 1 ||
			row.metadata.condition !== "summary" ||
			row.metadata.ablation !== null ||
			row.model_id !== source.model_key ||
			data.source.run_identity_sha256 !== source.run_identity_sha256 ||
			data.source.model_registry_sha256 !== source.model_registry_sha256
		)
			throw new Error("Summary condition does not match its source");
		if (!cache || source.summary_cache_sha256 !== cache)
			throw new Error("Summary inputs differ");
		if (
			data.excluded_case_count !== 0 ||
			data.contamination_boundary !== reference.contamination_boundary ||
			row.case_count !== referenceRow.case_count ||
			row.unit_count !== referenceRow.unit_count ||
			publicUnitCensus(row.units) !== census
		)
			throw new Error("Summary comparison cohort differs");
		return {
			slug: source.slug,
			display_name: row.model_id.includes("typesafe-ai/jev")
				? "Jev"
				: row.model_id.includes("gpt-6-luna")
					? "GPT-6 Luna"
					: "GPT-5.6 Luna",
			input_label: "GPT-5.6 Luna summaries · one shot",
			reasoning_label:
				row.metadata.reasoning_effort === "none"
					? "Off"
					: row.metadata.reasoning_effort === "high"
						? "High"
						: "Native probabilities",
			role:
				row.metadata.reasoning_effort === "high"
					? "reasoning-reference"
					: "comparison",
			micro_brier: row.micro_brier,
			equal_case_brier: row.equal_case_brier,
			correct: row.units.filter(
				(unit) =>
					Number(unit.probability_fully_dismissed >= 0.5) === unit.outcome,
			).length,
			unit_count: row.unit_count,
			case_count: row.case_count,
			forecast_run: source.forecast_run,
			source_url: `/data/exports/${source.slug}.json`,
			auc: rankAuc(row.units),
			mean_forecast: meanForecast(row.units),
			calibration: row.calibration,
			inference_usd: source.successful_inference_estimated_usd,
			preparation_usd: source.summary_preparation_estimated_usd,
		};
	});
	rows.sort(
		(a, b) => Number(a.role !== "comparison") - Number(b.role !== "comparison"),
	);
	rows.push({
		slug: "gpt-4-1",
		display_name: "GPT-4.1",
		input_label: "Full documents · agentic tools",
		reasoning_label: "Non-reasoning model",
		role: "full-record-reference",
		micro_brier: referenceRow.micro_brier,
		equal_case_brier: referenceRow.equal_case_brier,
		correct: referenceRow.units.filter(
			(unit) =>
				Number(unit.probability_fully_dismissed >= 0.5) === unit.outcome,
		).length,
		unit_count: referenceRow.unit_count,
		case_count: referenceRow.case_count,
		forecast_run: "35954543028",
		source_url: "/models/gpt-4-1/",
		auc: rankAuc(referenceRow.units),
		mean_forecast: meanForecast(referenceRow.units),
		calibration: referenceRow.calibration,
		inference_usd: null,
		preparation_usd: null,
	});
	return rows;
}

export const supplementaryRows = buildSupplementaryRows(
	summaryComparisons,
	parseSiteExport(gpt41),
);
