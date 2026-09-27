import type { SupplementaryRow } from "../data/supplementary-results";

interface Props {
	rows: SupplementaryRow[];
	/** Constant forecast at the cohort dismissal rate. */
	baseRateBrier: number;
}

const MAX = 0.65;
const pos = (v: number) => `${(Math.min(v, MAX) / MAX) * 100}%`;

/**
 * Micro Brier as horizontal bars (shorter is better) against two naive
 * references. HTML rather than SVG so labels stay legible on phones.
 */
export default function SummaryBrierChart({ rows, baseRateBrier }: Props) {
	const references = [
		{ value: baseRateBrier, label: "Base-rate forecast" },
		{ value: 0.25, label: "Always 50%" },
	];
	const groups = [
		{
			title: "Same GPT-5.6 Luna summaries, one shot",
			rows: rows.filter((r) => r.role !== "full-record-reference"),
		},
		{
			title: "Full record, agentic tools (older non-reasoning model)",
			rows: rows.filter((r) => r.role === "full-record-reference"),
		},
	];
	return (
		<figure className="not-serif m-0">
			<div
				className="relative mb-2 ml-[9.25rem] h-9 text-[11px] leading-tight text-ink-3 sm:ml-[12.75rem]"
				aria-hidden="true"
			>
				{references.map((ref, i) => (
					<span
						key={ref.label}
						className="absolute -translate-x-full whitespace-nowrap border-r border-dashed border-ink-3 pr-1.5 text-right sm:translate-x-0 sm:border-r-0 sm:border-l sm:pr-0 sm:pl-1.5 sm:text-left"
						style={{
							left: pos(ref.value),
							top: i === 0 ? "1.1rem" : 0,
							bottom: 0,
						}}
					>
						{ref.label} ({ref.value.toFixed(3)})
					</span>
				))}
			</div>
			<div className="space-y-6">
				{groups.map((group) => (
					<div key={group.title}>
						<p className="mb-2 text-xs font-medium text-ink-3">{group.title}</p>
						<ul className="space-y-2.5">
							{group.rows.map((row) => {
								const beatsBase = row.micro_brier < baseRateBrier;
								return (
									<li
										key={row.slug}
										className="grid grid-cols-[8.5rem_1fr] items-center gap-3 sm:grid-cols-[12rem_1fr]"
									>
										<span className="text-sm leading-tight text-ink">
											<span className="font-medium">{row.display_name}</span>
											<span className="block text-xs text-ink-3">
												Reasoning: {row.reasoning_label.toLowerCase()}
											</span>
										</span>
										<div className="relative h-7">
											{references.map((ref) => (
												<span
													key={ref.label}
													className="absolute inset-y-[-4px] w-px border-l border-dashed border-ink-3"
													style={{ left: pos(ref.value) }}
												/>
											))}
											<div
												className={`absolute inset-y-1 left-0 rounded-r-md ${beatsBase ? "bg-series-1" : "bg-ink-2"}`}
												style={{ width: pos(row.micro_brier) }}
											/>
											{row.micro_brier / MAX > 0.7 ? (
												<span
													className="absolute top-1/2 -translate-x-full -translate-y-1/2 pr-2 text-sm font-medium text-bg tabular"
													style={{ left: pos(row.micro_brier) }}
												>
													{row.micro_brier.toFixed(3)}
												</span>
											) : (
												<span
													className="absolute top-1/2 ml-1.5 -translate-y-1/2 rounded bg-surface px-1 text-sm font-medium text-ink tabular"
													style={{ left: pos(row.micro_brier) }}
												>
													{row.micro_brier.toFixed(3)}
												</span>
											)}
										</div>
									</li>
								);
							})}
						</ul>
					</div>
				))}
			</div>
			<figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-3">
				<span>
					Micro Brier: mean squared error over 387 units. Shorter bars are
					better.
				</span>
				<span className="inline-flex items-center gap-1.5">
					<span
						className="h-2.5 w-4 rounded-sm bg-series-1"
						aria-hidden="true"
					/>{" "}
					Beats the base-rate forecast
				</span>
				<span className="inline-flex items-center gap-1.5">
					<span className="h-2.5 w-4 rounded-sm bg-ink-2" aria-hidden="true" />{" "}
					Does not
				</span>
			</figcaption>
		</figure>
	);
}
