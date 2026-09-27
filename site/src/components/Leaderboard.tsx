import { useMemo, useState } from "react";
import { EXPLAIN } from "../data/explanations";
import {
	accuracy,
	formatPercent,
	formatUsd,
	METRICS,
	metricValue,
	paretoFrontier,
	ranks,
} from "../data/metrics";
import type { ResultsSnapshot, SnapshotModel } from "../data/snapshot";
import EligibilityBadge from "./EligibilityBadge";
import Tip from "./Tip";

type SortKey =
	| "micro_brier"
	| "equal_case_brier"
	| "accuracy"
	| "high_confidence"
	| "cost";

interface Column {
	key: SortKey;
	label: string;
	hint: string;
	/** Ascending sort is "better first" for these. */
	lowerIsBetter: boolean;
}

const COLUMNS: Column[] = [
	{
		key: "micro_brier",
		label: "Micro Brier",
		hint: "Headline. Mean squared error of the dismissal probability across all 387 units; every unit weighs the same. Lower is better.",
		lowerIsBetter: true,
	},
	{
		key: "equal_case_brier",
		label: "Equal-case",
		hint: "Sensitivity analysis. Averages each case's Brier first, so a case with many claims counts the same as a case with one. Lower is better.",
		lowerIsBetter: true,
	},
	{
		key: "accuracy",
		label: "Accuracy",
		hint: "Share of units where a probability of at least 50% matched dismissal. Ignores confidence.",
		lowerIsBetter: false,
	},
	{
		key: "high_confidence",
		label: "≥90% misses",
		hint: "Wrong predictions among those at least 90% confident either way. Scored units, not independent cases.",
		lowerIsBetter: true,
	},
	{
		key: "cost",
		label: "Cost",
		hint: "Estimated standard-rate API cost for the 91-case cohort. See the Data page for methodology.",
		lowerIsBetter: true,
	},
];

function sortValue(model: SnapshotModel, key: SortKey, n: number): number {
	switch (key) {
		case "accuracy":
			return accuracy(model, n);
		case "high_confidence":
			return model.high_confidence.count
				? model.high_confidence.wrong / model.high_confidence.count
				: 0;
		case "cost":
			return model.cost.usd ?? Number.POSITIVE_INFINITY;
		default:
			return model[key];
	}
}

function BrierRail({
	value,
	lo,
	hi,
	baseline,
}: {
	value: number;
	lo: number;
	hi: number;
	baseline: number;
}) {
	const pos = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
	return (
		<div
			className="relative mt-1.5 hidden h-1.5 w-28 rounded-full bg-surface-2 md:block"
			aria-hidden="true"
		>
			<div
				className="absolute inset-y-0 left-0 rounded-full bg-series-1-soft"
				style={{ width: pos(value) }}
			/>
			<div
				className="absolute -top-0.5 h-2.5 w-px bg-ink-3"
				style={{ left: pos(baseline) }}
			/>
			<div
				className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-series-1"
				style={{ left: pos(value) }}
			/>
		</div>
	);
}

export default function Leaderboard({
	snapshot,
}: {
	snapshot: ResultsSnapshot;
}) {
	const n = snapshot.cohort.unit_count;
	const [sort, setSort] = useState<{ key: SortKey; asc: boolean }>({
		key: "micro_brier",
		asc: true,
	});
	const frontier = useMemo(() => {
		const metrics = new Map<string, string[]>();
		for (const metric of [
			"micro_brier",
			"equal_case_brier",
			"accuracy",
		] as const) {
			for (const model of paretoFrontier(snapshot, metric)) {
				const labels = metrics.get(model.slug) ?? [];
				labels.push(METRICS[metric].label);
				metrics.set(model.slug, labels);
			}
		}
		return metrics;
	}, [snapshot]);
	const sigWorse = useMemo(() => {
		const map = new Map<string, string[]>();
		for (const pair of snapshot.significant_pairs) {
			const better =
				snapshot.models.find((m) => m.slug === pair.better)?.display_name ??
				pair.better;
			const list = map.get(pair.worse) ?? [];
			list.push(`${better} (${METRICS[pair.metric].label})`);
			map.set(pair.worse, list);
		}
		return map;
	}, [snapshot]);
	const rows = useMemo(() => {
		const sign = sort.asc ? 1 : -1;
		return [...snapshot.models].sort(
			(a, b) => sign * (sortValue(a, sort.key, n) - sortValue(b, sort.key, n)),
		);
	}, [snapshot, sort, n]);
	const briers = snapshot.models.map((m) => m.micro_brier);
	const railLo = Math.min(...briers) - 0.02;
	const railHi =
		Math.max(snapshot.cohort.constant_forecast_micro_brier, ...briers) + 0.01;
	const microRank = useMemo(() => ranks(snapshot, "micro_brier"), [snapshot]);

	const onSort = (column: Column) =>
		setSort((current) =>
			current.key === column.key
				? { key: column.key, asc: !current.asc }
				: { key: column.key, asc: column.lowerIsBetter },
		);

	return (
		<div className="not-serif card overflow-hidden">
			<div className="overflow-x-auto">
				<table className="w-full min-w-[760px] border-collapse text-sm">
					<caption className="sr-only">
						{snapshot.title}: {snapshot.models.length} models on{" "}
						{snapshot.cohort.case_count} cases and {n} units. Click a column to
						sort.
					</caption>
					<thead>
						<tr className="border-b border-rule text-left text-xs text-ink-3">
							<th scope="col" className="w-10 py-3 pl-4 font-medium">
								<Tip tip={EXPLAIN.rank} side="bottom" align="start">
									#
								</Tip>
							</th>
							<th scope="col" className="py-3 pr-4 font-medium">
								Model
							</th>
							{COLUMNS.map((column) => (
								<th
									key={column.key}
									scope="col"
									className="py-3 pr-4 font-medium"
									aria-sort={
										sort.key === column.key
											? sort.asc
												? "ascending"
												: "descending"
											: "none"
									}
								>
									<Tip
										tip={column.hint}
										side="bottom"
										align={column.key === "cost" ? "end" : "center"}
										focusable={false}
									>
										<button
											type="button"
											onClick={() => onSort(column)}
											className={`inline-flex items-center gap-1 underline decoration-dotted decoration-rule-strong underline-offset-4 hover:text-ink ${
												sort.key === column.key ? "text-ink" : ""
											}`}
										>
											{column.label}
											<span aria-hidden="true" className="text-[10px]">
												{sort.key === column.key ? (sort.asc ? "▲" : "▼") : ""}
											</span>
										</button>
									</Tip>
								</th>
							))}
							<th scope="col" className="py-3 pr-4 font-medium">
								<Tip
									tip="Whether the model's documented training cutoff predates every scored decision. Hover a badge for the model's specifics."
									side="bottom"
									align="end"
								>
									<span className="underline decoration-dotted decoration-rule-strong underline-offset-4">
										Cutoff
									</span>
								</Tip>
							</th>
						</tr>
					</thead>
					<tbody>
						{rows.map((model, index) => {
							const hc = model.high_confidence;
							// Prefer below early rows; Tip handles viewport collisions.
							const side = index < 3 ? "bottom" : "top";
							const worse = sigWorse.get(model.slug);
							return (
								<tr
									key={model.slug}
									className="group border-b border-rule last:border-0 hover:bg-surface-2/60"
								>
									<td className="py-3.5 pl-4 align-top text-ink-3 tabular">
										{microRank.get(model.slug)}
									</td>
									<td className="py-3.5 pr-4 align-top">
										<a
											href={`/models/${model.slug}/`}
											className="font-semibold text-ink decoration-accent/40 hover:underline"
										>
											{model.display_name}
										</a>
										<div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-3">
											<span>{model.provider}</span>
											{frontier.has(model.slug) && (
												<Tip
													side={side}
													align="start"
													tip={`Pareto frontier for: ${frontier.get(model.slug)?.join(", ")}. ${EXPLAIN.frontier}`}
												>
													<span className="inline-flex items-center gap-1 text-series-1 underline decoration-dotted underline-offset-2">
														<svg width="9" height="9" aria-hidden="true">
															<rect
																x="1.5"
																y="1.5"
																width="6"
																height="6"
																transform="rotate(45 4.5 4.5)"
																fill="currentColor"
															/>
														</svg>
														Pareto frontier
													</span>
												</Tip>
											)}
										</div>
										{worse && (
											<Tip
												tip={EXPLAIN.significance}
												side={side}
												align="start"
												className="mt-1"
											>
												<span className="block max-w-56 text-xs text-critical underline decoration-dotted underline-offset-2">
													{`Significantly worse than ${worse.join("; ")}`}
												</span>
											</Tip>
										)}
									</td>
									<td className="py-3.5 pr-4 align-top tabular">
										<span className="font-medium text-ink">
											{METRICS.micro_brier.format(model.micro_brier)}
										</span>
										<BrierRail
											value={model.micro_brier}
											lo={railLo}
											hi={railHi}
											baseline={snapshot.cohort.constant_forecast_micro_brier}
										/>
									</td>
									<td className="py-3.5 pr-4 align-top tabular text-ink-2">
										{METRICS.equal_case_brier.format(model.equal_case_brier)}
									</td>
									<td className="py-3.5 pr-4 align-top tabular text-ink-2">
										{formatPercent(metricValue(model, "accuracy", n))}
										<div className="text-xs text-ink-3">
											{model.correct}/{n}
										</div>
									</td>
									<td className="py-3.5 pr-4 align-top tabular text-ink-2">
										{hc.wrong} <span className="text-ink-3">of {hc.count}</span>
									</td>
									<td className="py-3.5 pr-4 align-top tabular text-ink-2">
										{formatUsd(model.cost.usd)}
									</td>
									<td className="py-3.5 pr-4 align-top">
										<EligibilityBadge
											eligibility={model.eligibility}
											reason={model.eligibility_reason}
											side={side}
											align="end"
										/>
									</td>
								</tr>
							);
						})}
					</tbody>
				</table>
			</div>
			<div className="grid gap-4 border-t border-rule px-4 py-4 text-xs leading-relaxed text-ink-2 md:grid-cols-2">
				<div>
					<a
						className="text-accent hover:underline"
						href="/data/beta-run-mechanics/#costs"
					>
						Cost methodology and explanations →
					</a>
				</div>
				<div>
					<p className="font-semibold text-ink">Qualified comparisons</p>
					<ul className="mt-1.5 space-y-1">
						{snapshot.models
							.filter((m) => m.eligibility !== "eligible")
							.map((m) => (
								<li key={m.slug}>
									<span className="font-medium text-ink">
										{m.display_name}:
									</span>{" "}
									{m.eligibility_reason}
								</li>
							))}
					</ul>
				</div>
			</div>
			<div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-rule bg-surface-2/50 px-4 py-3 text-xs text-ink-3">
				<span>
					Rail tick: constant base-rate forecast (
					{METRICS.micro_brier.format(
						snapshot.cohort.constant_forecast_micro_brier,
					)}
					)
				</span>
				<span># is the micro Brier rank, whatever the sort</span>
				<span>Hover a column name for its definition</span>
				<span>
					Eligible: documented training cutoff predates every scored decision
				</span>
			</div>
		</div>
	);
}
