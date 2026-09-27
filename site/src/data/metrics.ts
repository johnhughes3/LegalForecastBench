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
	return `$${value.toFixed(2)}`;
}

export function formatPercent(value: number, digits = 1): string {
	return `${(value * 100).toFixed(digits)}%`;
}

/**
 * Probability that a randomly chosen dismissed unit received a higher forecast
 * than a randomly chosen surviving unit (ROC AUC; ties count half). It measures
 * ranking ability separately from calibration.
 */
export function rankAuc(
	units: { probability_fully_dismissed: number; outcome: 0 | 1 }[],
): number {
	const positives = units
		.filter((u) => u.outcome === 1)
		.map((u) => u.probability_fully_dismissed);
	const negatives = units
		.filter((u) => u.outcome === 0)
		.map((u) => u.probability_fully_dismissed);
	if (positives.length === 0 || negatives.length === 0)
		throw new Error("AUC needs both outcomes");
	let wins = 0;
	for (const p of positives)
		for (const n of negatives) wins += p > n ? 1 : p === n ? 0.5 : 0;
	return wins / (positives.length * negatives.length);
}

export function meanForecast(
	units: { probability_fully_dismissed: number }[],
): number {
	return (
		units.reduce((sum, u) => sum + u.probability_fully_dismissed, 0) /
		units.length
	);
}
