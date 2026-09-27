import type { Metric, ResultsSnapshot, SnapshotModel } from "./snapshot.js";

export interface MetricSpec {
	key: Metric;
	label: string;
	short: string;
	direction: "lower" | "higher";
	format: (value: number) => string;
}

export const METRICS: Record<Metric, MetricSpec> = {
	micro_brier: {
		key: "micro_brier",
		label: "Micro Brier",
		short: "Micro",
		direction: "lower",
		format: (v) => v.toFixed(4),
	},
	equal_case_brier: {
		key: "equal_case_brier",
		label: "Equal-case Brier",
		short: "Equal-case",
		direction: "lower",
		format: (v) => v.toFixed(4),
	},
	accuracy: {
		key: "accuracy",
		label: "Unit accuracy",
		short: "Accuracy",
		direction: "higher",
		format: (v) => `${(v * 100).toFixed(1)}%`,
	},
};

export function accuracy(model: SnapshotModel, unitCount: number): number {
	return model.correct / unitCount;
}

export function metricValue(
	model: SnapshotModel,
	metric: Metric,
	unitCount: number,
): number {
	return metric === "accuracy" ? accuracy(model, unitCount) : model[metric];
}

/** True when `a` is strictly better than `b` on the metric. */
export function better(metric: Metric, a: number, b: number): boolean {
	return METRICS[metric].direction === "lower" ? a < b : a > b;
}

/**
 * Observed cost/quality Pareto frontier: models that no other model beats on
 * both cost and the metric. Membership is descriptive, not a significance claim.
 * Models without a cost are excluded rather than treated as free.
 */
export function paretoFrontier(
	snapshot: ResultsSnapshot,
	metric: Metric,
): SnapshotModel[] {
	const n = snapshot.cohort.unit_count;
	const priced = snapshot.models.filter((m) => m.cost.usd !== null);
	return priced
		.filter((m) => {
			const cost = m.cost.usd as number;
			const value = metricValue(m, metric, n);
			return !priced.some((o) => {
				if (o === m) return false;
				const oCost = o.cost.usd as number;
				const oValue = metricValue(o, metric, n);
				const noWorse = oCost <= cost && !better(metric, value, oValue);
				const strictly = oCost < cost || better(metric, oValue, value);
				return noWorse && strictly;
			});
		})
		.sort((a, b) => (a.cost.usd as number) - (b.cost.usd as number));
}

/** Competition ranks (1, 2, 2, 4) on a metric. */
export function ranks(
	snapshot: ResultsSnapshot,
	metric: Metric,
): Map<string, number> {
	const n = snapshot.cohort.unit_count;
	const values = snapshot.models.map((m) => ({
		slug: m.slug,
		v: metricValue(m, metric, n),
	}));
	const result = new Map<string, number>();
	for (const { slug, v } of values) {
		result.set(slug, 1 + values.filter((o) => better(metric, o.v, v)).length);
	}
	return result;
}

export function sortedBy(
	snapshot: ResultsSnapshot,
	metric: Metric,
): SnapshotModel[] {
	const n = snapshot.cohort.unit_count;
	const sign = METRICS[metric].direction === "lower" ? 1 : -1;
	return [...snapshot.models].sort(
		(a, b) => sign * (metricValue(a, metric, n) - metricValue(b, metric, n)),
	);
}

export function formatUsd(value: number | null): string {
	if (value === null) return "Unknown";
	return value < 10 ? `$${value.toFixed(2)}` : `$${value.toFixed(2)}`;
}

export function formatPercent(value: number, digits = 1): string {
	return `${(value * 100).toFixed(digits)}%`;
}
