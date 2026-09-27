import type { ResultsSnapshot } from "../data/snapshot";

const HI = 1.0;

/**
 * Stated versus realized accuracy within each model's high-confidence
 * predictions (at least 90% either way). HTML rows rather than one SVG so the
 * text stays legible when the chart stacks on narrow screens.
 */
export default function ConfidenceChart({
	snapshot,
	highlight,
}: {
	snapshot: ResultsSnapshot;
	highlight?: string;
}) {
	const rows = snapshot.models
		.filter(
			(m) =>
				m.high_confidence.count > 0 &&
				m.high_confidence.mean_confidence !== null,
		)
		.map((m) => {
			const stated = m.high_confidence.mean_confidence as number;
			const realized = 1 - m.high_confidence.wrong / m.high_confidence.count;
			return { m, stated, realized, gap: stated - realized };
		})
		.sort((a, b) => b.gap - a.gap);
	// Start the axis just below the lowest value so differences near 90-100%
	// stay visible; reference models are excluded upstream, not squeezed in.
	const lowest = Math.min(...rows.flatMap((r) => [r.stated, r.realized]));
	const LO = Math.max(0.5, Math.floor((lowest - 0.01) * 20) / 20);
	const TICKS = Array.from(
		{ length: Math.round((HI - LO) / 0.05) + 1 },
		(_, i) => Number((LO + i * 0.05).toFixed(2)),
	).filter((t, i, all) => all.length <= 6 || i % 2 === 0 || t === HI);
	const pos = (v: number) => `${((Math.max(v, LO) - LO) / (HI - LO)) * 100}%`;

	return (
		<figure className="not-serif m-0">
			<div className="hidden grid-cols-[9.5rem_1fr_10rem] gap-4 pb-2 text-xs text-ink-3 sm:grid">
				<span />
				<span>Share of high-confidence predictions that were right</span>
				<span>Misses / predictions ≥90%</span>
			</div>
			<ul className="divide-y divide-rule sm:divide-y-0">
				{rows.map(({ m, stated, realized }) => {
					const dim = highlight !== undefined && highlight !== m.slug;
					const summary = `${m.display_name}: mean stated confidence ${(stated * 100).toFixed(1)}%, realized accuracy ${(realized * 100).toFixed(1)}% on ${m.high_confidence.count} predictions`;
					return (
						<li
							key={m.slug}
							className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1.5 py-2.5 sm:grid-cols-[9.5rem_1fr_10rem] sm:py-1.5"
						>
							{/* Other models recede: marks fade, text drops to the muted ink
							    (which keeps 4.5:1) rather than fading below legibility. */}
							<span
								className={`col-start-1 row-start-1 text-sm sm:text-right ${highlight === m.slug ? "font-semibold text-ink" : dim ? "font-normal text-ink-3" : "font-medium text-ink"}`}
							>
								{m.display_name}
							</span>
							<div
								className={`relative col-span-2 col-start-1 row-start-2 mx-2 h-5 sm:mx-0 sm:col-span-1 sm:col-start-2 sm:row-start-1 ${dim ? "opacity-35" : ""}`}
								title={summary}
							>
								{TICKS.map((t) => (
									<span
										key={t}
										className="absolute inset-y-0 w-px bg-rule"
										style={{ left: pos(t) }}
									/>
								))}
								<span
									className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-rule-strong"
									style={{
										left: pos(Math.min(stated, realized)),
										right: `calc(100% - ${pos(Math.max(stated, realized))})`,
									}}
								/>
								<span
									className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink-2 bg-surface"
									style={{ left: pos(stated) }}
								/>
								<span
									className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-series-1 ring-2 ring-surface"
									style={{ left: pos(realized) }}
								/>
								<span className="sr-only">{summary}</span>
							</div>
							<span
								className={`col-start-2 row-start-1 text-right text-xs tabular sm:col-start-3 sm:text-left sm:text-sm ${dim ? "text-ink-3" : "text-ink-2"}`}
							>
								{m.high_confidence.wrong} / {m.high_confidence.count}
								<span className="text-ink-3">
									{" "}
									(
									{(
										(m.high_confidence.count / snapshot.cohort.unit_count) *
										100
									).toFixed(0)}
									% of units)
								</span>
							</span>
						</li>
					);
				})}
			</ul>
			<div className="relative mx-2 mt-1 h-4 text-[11px] text-ink-3 sm:mr-[11rem] sm:ml-[10.5rem]">
				{TICKS.map((t) => (
					<span
						key={t}
						className="absolute -translate-x-1/2 tabular"
						style={{ left: pos(t) }}
					>
						{Math.round(t * 100)}%
					</span>
				))}
			</div>
			<figcaption className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-3">
				<span className="inline-flex items-center gap-1.5">
					<span
						className="size-2.5 rounded-full border-2 border-ink-2"
						aria-hidden="true"
					/>
					Mean stated confidence
				</span>
				<span className="inline-flex items-center gap-1.5">
					<span
						className="size-2.5 rounded-full bg-series-1"
						aria-hidden="true"
					/>
					Realized accuracy
				</span>
				<span>
					Sorted by the gap between them. Units, not independent cases: several
					misses can come from one case.
				</span>
			</figcaption>
		</figure>
	);
}
