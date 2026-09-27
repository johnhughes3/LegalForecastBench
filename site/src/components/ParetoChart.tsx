import { useMemo, useState } from "react";
import {
	formatUsd,
	METRICS,
	metricValue,
	paretoFrontier,
	ranks,
} from "../data/metrics";
import type { Metric, ResultsSnapshot, SnapshotModel } from "../data/snapshot";
import { useWidth } from "./useWidth";

interface Props {
	snapshot: ResultsSnapshot;
	initialMetric?: Metric;
	/** Emphasize one model (model pages); others recede. */
	highlight?: string;
	showToggle?: boolean;
}

interface Placed {
	model: SnapshotModel;
	x: number;
	y: number;
	frontier: boolean;
	label: { x: number; y: number; anchor: "start" | "middle" | "end" } | null;
}

type Label = NonNullable<Placed["label"]>;

// Measured mean glyph advance of 12px Inter labels at weights 450 and 600.
const LABEL_CHAR = { regular: 6.4, bold: 7 };
// Configuration stays in tooltips and model pages; labels retain the model/version.
const chartLabel = (model: SnapshotModel) =>
	model.display_name.replace(/\s*\([^)]*\)/g, "");

function niceTicks(lo: number, hi: number, step: number): number[] {
	const ticks: number[] = [];
	for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step)
		ticks.push(Number(v.toFixed(6)));
	return ticks;
}

type Box = { x0: number; x1: number; y0: number; y1: number };

/**
 * Greedy label placement: score candidate positions by overlap with points,
 * the frontier line, and earlier labels; stay inside the plot when possible.
 * Covering a point hides data, so point overlap costs more than label overlap.
 */
function placeLabels(
	points: Omit<Placed, "label">[],
	width: number,
	obstacles: Box[],
	labeled: (p: Omit<Placed, "label">) => boolean,
	bold: (p: Omit<Placed, "label">) => boolean,
): Placed[] {
	const marks: Box[] = points.map((p) => ({
		x0: p.x - 8,
		x1: p.x + 8,
		y0: p.y - 8,
		y1: p.y + 8,
	}));
	const boxes: Box[] = [...obstacles];
	const area = (b: Box, list: Box[]) =>
		list.reduce((sum, o) => {
			const w = Math.min(b.x1, o.x1) - Math.max(b.x0, o.x0);
			const h = Math.min(b.y1, o.y1) - Math.max(b.y0, o.y0);
			return w > 0 && h > 0 ? sum + w * h : sum;
		}, 0);
	const overlap = (b: Box) => area(b, boxes) + 4 * area(b, marks);
	return [...points]
		.sort((a, b) => Number(labeled(b)) - Number(labeled(a)) || a.y - b.y)
		.map((p) => {
			if (!labeled(p)) return { ...p, label: null };
			const w =
				chartLabel(p.model).length *
				(bold(p) ? LABEL_CHAR.bold : LABEL_CHAR.regular);
			const candidates: Label[] = [
				{ x: p.x + 10, y: p.y + 4, anchor: "start" },
				{ x: p.x - 10, y: p.y + 4, anchor: "end" },
				{ x: p.x + 4, y: p.y + 19, anchor: "start" },
				{ x: p.x - 4, y: p.y + 19, anchor: "end" },
				{ x: p.x + 4, y: p.y - 11, anchor: "start" },
				{ x: p.x - 4, y: p.y - 11, anchor: "end" },
				{ x: p.x, y: p.y - 13, anchor: "middle" },
				{ x: p.x, y: p.y + 22, anchor: "middle" },
				{ x: p.x + 10, y: p.y - 6, anchor: "start" },
				{ x: p.x - 10, y: p.y - 6, anchor: "end" },
				{ x: p.x + 10, y: p.y + 14, anchor: "start" },
				{ x: p.x - 10, y: p.y + 14, anchor: "end" },
			];
			const lead = { start: 0, middle: w / 2, end: w };
			const box = (c: Label): Box => ({
				x0: c.x - lead[c.anchor],
				x1: c.x - lead[c.anchor] + w,
				y0: c.y - 11,
				y1: c.y + 3,
			});
			const score = (c: Label) => {
				const b = box(c);
				const outside = Math.max(0, 2 - b.x0) + Math.max(0, b.x1 - (width - 2));
				return overlap(b) + outside * 1000 + candidates.indexOf(c);
			};
			const label = candidates.reduce((best, c) =>
				score(c) < score(best) ? c : best,
			);
			boxes.push(box(label));
			return { ...p, label };
		});
}

/** Sample a polyline into small boxes so labels avoid it. */
function lineObstacles(path: { x: number; y: number }[]): Box[] {
	const out: Box[] = [];
	for (let i = 1; i < path.length; i++) {
		const a = path[i - 1] as { x: number; y: number };
		const b = path[i] as { x: number; y: number };
		const steps = Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / 8);
		for (let k = 0; k <= steps; k++) {
			const x = a.x + ((b.x - a.x) * k) / steps;
			const y = a.y + ((b.y - a.y) * k) / steps;
			out.push({ x0: x - 2, x1: x + 2, y0: y - 2, y1: y + 2 });
		}
	}
	return out;
}

export default function ParetoChart({
	snapshot,
	initialMetric = "micro_brier",
	highlight,
	showToggle = true,
}: Props) {
	const [metric, setMetric] = useState<Metric>(initialMetric);
	const [hover, setHover] = useState<string | null>(null);
	const [ref, width] = useWidth<HTMLDivElement>(760);
	const spec = METRICS[metric];
	const n = snapshot.cohort.unit_count;
	const height = Math.max(360, Math.min(560, width * 0.75));
	const narrow = width < 560;
	const m = { top: 34, right: 12, bottom: 46, left: narrow ? 46 : 54 };
	const plotW = width - m.left - m.right;
	const plotH = height - m.top - m.bottom;

	const baseline =
		metric === "micro_brier"
			? {
					value: snapshot.cohort.constant_forecast_micro_brier,
					label: "Constant base-rate forecast",
				}
			: metric === "accuracy"
				? {
						value: snapshot.cohort.majority_class_accuracy,
						label: "Always predict dismissal",
					}
				: null;

	const layout = useMemo(() => {
		const priced = snapshot.models.filter((model) => model.cost.usd !== null);
		const costs = priced.map((model) => model.cost.usd as number);
		const x0 = Math.log10(Math.min(...costs) * 0.6);
		const x1 = Math.log10(Math.max(...costs) * 1.7);
		const values = priced.map((model) => metricValue(model, metric, n));
		if (baseline) values.push(baseline.value);
		const pad = (Math.max(...values) - Math.min(...values)) * 0.08;
		const lo = Math.min(...values) - pad;
		const hi = Math.max(...values) + pad;
		const sx = (usd: number) =>
			m.left + ((Math.log10(usd) - x0) / (x1 - x0)) * plotW;
		// Better is always drawn upward: lower Brier sits at the top.
		const sy = (v: number) =>
			spec.direction === "lower"
				? m.top + ((v - lo) / (hi - lo)) * plotH
				: m.top + ((hi - v) / (hi - lo)) * plotH;
		const frontier = paretoFrontier(snapshot, metric);
		const frontierSlugs = new Set(frontier.map((f) => f.slug));
		const frontierPath = frontier.map((f) => ({
			x: sx(f.cost.usd as number),
			y: sy(metricValue(f, metric, n)),
		}));
		// The baseline's own caption (right-aligned above its line) is an obstacle too.
		const baselineCaption: Box[] = baseline
			? [
					{
						x1: width - m.right - 4,
						x0:
							width -
							m.right -
							4 -
							`${baseline.label} (${spec.format(baseline.value)})`.length * 6,
						y0: sy(baseline.value) - 17,
						y1: sy(baseline.value) - 3,
					},
				]
			: [];
		const points = placeLabels(
			priced.map((model) => ({
				model,
				x: sx(model.cost.usd as number),
				y: sy(metricValue(model, metric, n)),
				frontier: frontierSlugs.has(model.slug),
			})),
			width,
			[...lineObstacles(frontierPath), ...baselineCaption],
			// Desktop labels every point; phones label the frontier, focus, and
			// worst score, and other names appear on tap.
			(p) =>
				!narrow ||
				p.frontier ||
				p.model.slug === highlight ||
				metricValue(p.model, metric, n) ===
					(spec.direction === "lower"
						? Math.max(...values)
						: Math.min(...values)),
			(p) => p.frontier || p.model.slug === highlight,
		);
		const xTicks = [0.5, 1, 2, 5, 10, 20, 50, 100, 200].filter(
			(t) => Math.log10(t) >= x0 && Math.log10(t) <= x1,
		);
		// Adapt tick density when an outlier expands the range: fixed 0.01 steps
		// would crowd every grid label after adding the older GPT-4.1 run.
		const rawStep = (hi - lo) / 6;
		const magnitude = 10 ** Math.floor(Math.log10(rawStep));
		const step =
			[1, 2, 5, 10]
				.map((factor) => factor * magnitude)
				.find((candidate) => candidate >= rawStep) ?? magnitude * 10;
		const yTicks = niceTicks(lo, hi, step);
		return { sx, sy, points, frontier, xTicks, yTicks };
	}, [
		snapshot,
		metric,
		n,
		baseline,
		m.left,
		m.top,
		plotW,
		plotH,
		spec.direction,
		width,
		narrow,
		highlight,
		spec.format,
		m.right,
	]);

	const rankMap = useMemo(() => ranks(snapshot, metric), [snapshot, metric]);
	const hovered = layout.points.find((p) => p.model.slug === hover);
	const excluded = snapshot.models.filter((model) => model.cost.usd === null);

	return (
		<figure className="not-serif m-0">
			{showToggle && (
				<div className="mb-4 flex flex-wrap items-center gap-3">
					<fieldset className="inline-flex rounded-full border border-rule bg-surface p-1 text-sm">
						<legend className="sr-only">Quality metric</legend>
						{(Object.keys(METRICS) as Metric[]).map((key) => (
							<button
								key={key}
								type="button"
								onClick={() => setMetric(key)}
								aria-pressed={metric === key}
								className={`rounded-full px-3.5 py-1.5 transition ${
									metric === key
										? "bg-ink text-bg shadow-sm"
										: "text-ink-2 hover:text-ink"
								}`}
							>
								<span className="hidden sm:inline">{METRICS[key].label}</span>
								<span className="sm:hidden">{METRICS[key].short}</span>
							</button>
						))}
					</fieldset>
					<span className="text-xs text-ink-3">
						{metric === "micro_brier"
							? "Headline metric"
							: metric === "equal_case_brier"
								? "Sensitivity analysis"
								: "Secondary"}
					</span>
				</div>
			)}
			{/* The CSS height repeats the `height` formula in container units, so the
			    server-rendered chart reserves the same box it has after hydration. */}
			<div ref={ref} className="@container relative w-full">
				{/* biome-ignore lint/a11y/useSemanticElements: an SVG cannot be a fieldset; role="group" lets the point links stay reachable (role="img" would hide them). */}
				<svg
					viewBox={`0 0 ${width} ${height}`}
					role="group"
					aria-label={`Cost versus ${spec.label} for ${layout.points.length} plotted models. Frontier: ${layout.frontier.map((f) => f.display_name).join(", ")}. Each point links to its model page.`}
					className="block h-[clamp(360px,75cqw,560px)] w-full overflow-visible"
				>
					{/* Axes and reference lines are visual; the group label and the
					    point links carry the content for assistive technology. */}
					{/* biome-ignore lint/a11y/noAriaHiddenOnFocusable: decorative SVG group with no focusable content. */}
					<g aria-hidden="true">
						{/* grid */}
						{layout.yTicks.map((t) => (
							<g key={`y${t}`}>
								<line
									x1={m.left}
									x2={width - m.right}
									y1={layout.sy(t)}
									y2={layout.sy(t)}
									stroke="var(--chart-grid)"
								/>
								<text
									x={m.left - 8}
									y={layout.sy(t) + 4}
									textAnchor="end"
									fontSize={11}
									fill="var(--ink-3)"
									className="tabular"
								>
									{spec.format(t)}
								</text>
							</g>
						))}
						{layout.xTicks.map((t) => (
							<g key={`x${t}`}>
								<line
									x1={layout.sx(t)}
									x2={layout.sx(t)}
									y1={m.top}
									y2={height - m.bottom}
									stroke="var(--chart-grid)"
								/>
								<text
									x={layout.sx(t)}
									y={height - m.bottom + 18}
									textAnchor="middle"
									fontSize={11}
									fill="var(--ink-3)"
									className="tabular"
								>
									{formatUsd(t).replace(".00", "")}
								</text>
							</g>
						))}
						<text
							x={m.left + plotW / 2}
							y={height - 6}
							textAnchor="middle"
							fontSize={11.5}
							fill="var(--ink-2)"
						>
							{narrow
								? "Cohort cost, log scale · cheaper ←"
								: `Standard-rate cost for the ${snapshot.cohort.case_count}-case cohort (log scale) · cheaper ←`}
						</text>
						<text
							x={m.left - 8}
							y={14}
							textAnchor="start"
							fontSize={11.5}
							fontWeight={500}
							fill="var(--ink-2)"
						>
							{spec.label} · better ↑
						</text>

						{baseline && (
							<g>
								<line
									x1={m.left}
									x2={width - m.right}
									y1={layout.sy(baseline.value)}
									y2={layout.sy(baseline.value)}
									stroke="var(--chart-muted)"
									strokeDasharray="2 4"
									strokeWidth={1.5}
								/>
								<text
									x={width - m.right - 4}
									y={layout.sy(baseline.value) - 6}
									textAnchor="end"
									fontSize={11}
									fill="var(--ink-3)"
								>
									{baseline.label} ({spec.format(baseline.value)})
								</text>
							</g>
						)}

						<polyline
							points={layout.frontier
								.map(
									(f) =>
										`${layout.sx(f.cost.usd as number)},${layout.sy(metricValue(f, metric, n))}`,
								)
								.join(" ")}
							fill="none"
							stroke="var(--series-1)"
							strokeWidth={2}
							strokeDasharray="6 5"
							strokeLinecap="round"
						/>
					</g>

					{layout.points.map((p) => {
						const dim =
							(highlight && highlight !== p.model.slug) ||
							(hover && hover !== p.model.slug);
						const color = p.frontier ? "var(--series-1)" : "var(--ink-2)";
						return (
							<g key={p.model.slug}>
								{/* Dimming fades the mark only; the label switches to the
								    muted ink so it stays legible (4.5:1) in both themes. */}
								{/* biome-ignore lint/a11y/noAriaHiddenOnFocusable: the mark is decorative; the sibling link names the point. */}
								<g
									aria-hidden="true"
									opacity={dim ? 0.35 : 1}
									style={{ transition: "opacity 150ms" }}
								>
									{p.frontier ? (
										<rect
											x={p.x - 6.5}
											y={p.y - 6.5}
											width={13}
											height={13}
											transform={`rotate(45 ${p.x} ${p.y})`}
											fill={color}
											stroke="var(--surface)"
											strokeWidth={2}
											rx={2}
										/>
									) : (
										<circle
											cx={p.x}
											cy={p.y}
											r={5.5}
											fill={color}
											stroke="var(--surface)"
											strokeWidth={2}
										/>
									)}
								</g>
								{p.label && (
									// biome-ignore lint/a11y/noAriaHiddenOnFocusable: the visible label duplicates the link's accessible name.
									<text
										aria-hidden="true"
										x={p.label.x}
										y={p.label.y}
										textAnchor={p.label.anchor}
										fontSize={12}
										fontWeight={
											!dim && (p.frontier || highlight === p.model.slug)
												? 600
												: 450
										}
										fill={
											dim
												? "var(--ink-3)"
												: p.frontier
													? "var(--ink)"
													: "var(--ink-2)"
										}
										stroke="var(--surface)"
										strokeWidth={4}
										strokeLinejoin="round"
										paintOrder="stroke"
									>
										{chartLabel(p.model)}
									</text>
								)}
								<a
									href={`/models/${p.model.slug}/`}
									aria-label={`${p.model.display_name} details`}
									onMouseEnter={() => setHover(p.model.slug)}
									onMouseLeave={() => setHover(null)}
									onFocus={() => setHover(p.model.slug)}
									onBlur={() => setHover(null)}
								>
									<title>{`${p.model.display_name}: ${spec.label} ${spec.format(metricValue(p.model, metric, n))}, cost ${formatUsd(p.model.cost.usd)}`}</title>
									<circle cx={p.x} cy={p.y} r={16} fill="transparent" />
								</a>
							</g>
						);
					})}
				</svg>
				{hovered && (
					<div
						className="pointer-events-none absolute z-10 w-60 max-w-full rounded-xl border border-rule bg-surface p-3 text-sm shadow-lg"
						style={{
							left: Math.max(0, Math.min(hovered.x - 120, width - 240)),
							// Anchor by the edge nearest the point so the card never covers
							// it, whatever its height (the cost note adds a wrapped line).
							...(hovered.y > height / 2
								? { bottom: height - hovered.y + 18 }
								: { top: hovered.y + 18 }),
						}}
					>
						<p className="font-semibold text-ink">
							{hovered.model.display_name}
						</p>
						<p className="text-xs text-ink-3">
							{hovered.model.provider} · {hovered.model.reasoning} reasoning
						</p>
						<dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 tabular">
							<dt className="text-ink-3">{spec.label}</dt>
							<dd className="text-right text-ink">
								{spec.format(metricValue(hovered.model, metric, n))}
							</dd>
							<dt className="text-ink-3">Rank</dt>
							<dd className="text-right text-ink">
								{rankMap.get(hovered.model.slug)} of {snapshot.models.length}
							</dd>
							<dt className="text-ink-3">Cost</dt>
							<dd className="text-right text-ink">
								{formatUsd(hovered.model.cost.usd)}
							</dd>
						</dl>
						{hovered.model.cost.note && (
							<p className="mt-1 text-xs text-ink-3">
								Estimated or adjusted cost; see the model page.
							</p>
						)}
						{hovered.frontier && (
							<p className="mt-2 text-xs font-medium text-series-1">
								On the observed frontier
							</p>
						)}
					</div>
				)}
			</div>
			<figcaption className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-ink-3">
				<span className="inline-flex items-center gap-1.5">
					<svg width="12" height="12" aria-hidden="true">
						<rect
							x="2"
							y="2"
							width="8"
							height="8"
							transform="rotate(45 6 6)"
							fill="var(--series-1)"
						/>
					</svg>
					Observed cost/quality frontier (descriptive, not significance)
				</span>
				<span className="inline-flex items-center gap-1.5">
					<svg width="12" height="12" aria-hidden="true">
						<circle cx="6" cy="6" r="4" fill="var(--ink-2)" />
					</svg>
					Other models
				</span>
				{narrow && <span>Tap a point to identify it.</span>}
				{excluded.length > 0 && (
					<span>
						Omitted without cost:{" "}
						{excluded.map((e) => e.display_name).join(", ")}
					</span>
				)}
			</figcaption>
		</figure>
	);
}
