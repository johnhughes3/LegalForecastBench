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

/** The value a phone card shows for the active sort column. */
function activeValue(model: SnapshotModel, key: SortKey, n: number): string {
	switch (key) {
		case "micro_brier":
			return METRICS.micro_brier.format(model.micro_brier);
		case "equal_case_brier":
			return METRICS.equal_case_brier.format(model.equal_case_brier);
		case "accuracy":
			return formatPercent(metricValue(model, "accuracy", n));
		case "high_confidence":
			return `${model.high_confidence.wrong} of ${model.high_confidence.count}`;
		case "cost":
			return formatUsd(model.cost.usd);
	}
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
			{/* Phones: one card per model; the full table is available from md up. */}
			<div className="md:hidden">
				<div className="flex items-center justify-between gap-3 border-b border-rule px-4 py-3 text-xs text-ink-3">
					<label htmlFor="lb-sort">Sort by</label>
					<select
						id="lb-sort"
						value={sort.key}
						onChange={(event) => {
							const column = COLUMNS.find((c) => c.key === event.target.value);
							if (column)
								setSort({ key: column.key, asc: column.lowerIsBetter });
						}}
						className="rounded-full border border-rule-strong bg-surface px-3 py-1.5 text-sm text-ink"
					>
						{COLUMNS.map((column) => (
							<option key={column.key} value={column.key}>
								{column.label}
							</option>
						))}
					</select>
				</div>
				<ol className="divide-y divide-rule">
					{rows.map((model, index) => {
						const active =
							COLUMNS.find((c) => c.key === sort.key) ?? COLUMNS[0];
						return (
							<li key={model.slug} className="flex gap-3 px-4 py-3.5">
								<span className="w-6 shrink-0 pt-0.5 text-sm text-ink-3 tabular">
									{microRank.get(model.slug)}
								</span>
								<div className="min-w-0 flex-1">
									<a
										href={`/models/${model.slug}/`}
										className="block truncate font-semibold text-ink hover:underline"
									>
										{model.display_name}
									</a>
									<div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3">
										<span>{model.provider}</span>
										{/* The right column already shows micro Brier when it is the sort. */}
										{sort.key !== "micro_brier" && (
											<span className="tabular">
												Micro {METRICS.micro_brier.format(model.micro_brier)}
											</span>
										)}
										{sort.key !== "cost" && (
											<span className="tabular">
												{formatUsd(model.cost.usd)}
											</span>
										)}
										{frontier.has(model.slug) && (
											<span className="text-series-1">◆ Frontier</span>
										)}
									</div>
								</div>
								<div className="flex shrink-0 flex-col items-end gap-1.5 text-right">
									<span className="font-medium text-ink tabular">
										{activeValue(model, active?.key ?? "micro_brier", n)}
									</span>
									<span className="text-[11px] text-ink-3">
										{active?.label}
									</span>
									<EligibilityBadge
										eligibility={model.eligibility}
										reason={model.eligibility_reason}
										side={index < 3 ? "bottom" : "top"}
										align="end"
									/>
								</div>
							</li>
						);
					})}
				</ol>
			</div>
			<div className="hidden overflow-x-auto md:block">
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
									tip="Whether the provider-reported training or knowledge cutoff predates the first scored decision. Hover a badge for the model's specifics."
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
			<div className="border-t border-rule px-4 py-4 text-xs leading-relaxed text-ink-2">
				<div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
					<p className="font-semibold text-ink">Qualified comparisons</p>
					<a className="text-accent" href="/data/costs.json" download>
						Cost evidence (JSON) →
					</a>
				</div>
				<ul className="mt-2 gap-x-8 md:columns-2">
					{snapshot.models
						.filter((m) => m.eligibility !== "eligible")
						.map((m) => (
							<li key={m.slug} className="mb-1 break-inside-avoid">
								<span className="font-medium text-ink">{m.display_name}:</span>{" "}
								{m.eligibility_reason}
							</li>
						))}
				</ul>
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
					Eligible: reported training or knowledge cutoff predates the first
					scored decision
				</span>
			</div>
		</div>
	);
}
