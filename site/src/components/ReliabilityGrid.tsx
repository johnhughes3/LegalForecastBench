import type { SupplementaryRow } from "../data/supplementary-results";

interface Props {
	rows: SupplementaryRow[];
	baseRate: number;
}

const S = 220;
const PAD = { l: 34, r: 10, t: 10, b: 30 };
const W = S - PAD.l - PAD.r;
const H = S - PAD.t - PAD.b;
const sx = (v: number) => PAD.l + v * W;
const sy = (v: number) => PAD.t + (1 - v) * H;

/**
 * One reliability diagram per condition, from the scorer's calibration bins.
 * Points on the diagonal are calibrated; points above it forecast too low.
 */
export default function ReliabilityGrid({ rows, baseRate }: Props) {
	return (
		<figure className="not-serif m-0">
			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
				{rows.map((row) => {
					const bins = row.calibration.filter(
						(b) =>
							b.unit_count > 0 &&
							b.mean_probability !== null &&
							b.observed_rate !== null,
					);
					const label = `${row.display_name}: mean forecast ${(row.mean_forecast * 100).toFixed(0)}% versus ${(baseRate * 100).toFixed(0)}% actually dismissed`;
					return (
						<div key={row.slug} className="rounded-xl border border-rule p-3">
							<p className="text-sm font-medium text-ink">{row.display_name}</p>
							<p className="text-xs text-ink-3">
								{row.role === "full-record-reference"
									? "Full record"
									: "Summaries"}{" "}
								· reasoning {row.reasoning_label.toLowerCase()}
							</p>
							<svg
								viewBox={`0 0 ${S} ${S}`}
								className="mt-2 block h-auto w-full"
								role="img"
								aria-label={label}
							>
								{[0, 0.5, 1].map((t) => (
									<g key={t}>
										<line
											x1={sx(t)}
											x2={sx(t)}
											y1={PAD.t}
											y2={PAD.t + H}
											stroke="var(--chart-grid)"
										/>
										<line
											x1={PAD.l}
											x2={PAD.l + W}
											y1={sy(t)}
											y2={sy(t)}
											stroke="var(--chart-grid)"
										/>
										<text
											x={sx(t)}
											y={S - 14}
											textAnchor="middle"
											fontSize={10}
											fill="var(--ink-3)"
										>
											{t * 100}%
										</text>
										<text
											x={PAD.l - 5}
											y={sy(t) + 3}
											textAnchor="end"
											fontSize={10}
											fill="var(--ink-3)"
										>
											{t * 100}%
										</text>
									</g>
								))}
								<line
									x1={sx(0)}
									y1={sy(0)}
									x2={sx(1)}
									y2={sy(1)}
									stroke="var(--rule-strong)"
									strokeWidth={1.5}
								/>
								<line
									x1={PAD.l}
									x2={PAD.l + W}
									y1={sy(baseRate)}
									y2={sy(baseRate)}
									stroke="var(--chart-muted)"
									strokeDasharray="2 3"
								/>
								<line
									x1={sx(row.mean_forecast)}
									x2={sx(row.mean_forecast)}
									y1={PAD.t}
									y2={PAD.t + H}
									stroke="var(--accent)"
									strokeDasharray="4 3"
									strokeWidth={1.5}
								/>
								{bins.map((b) => (
									<circle
										key={b.lower}
										cx={sx(b.mean_probability as number)}
										cy={sy(b.observed_rate as number)}
										r={Math.max(2.5, Math.sqrt(b.unit_count) * 1.1)}
										fill="var(--series-1)"
										fillOpacity={0.75}
										stroke="var(--surface)"
										strokeWidth={1.5}
									>
										<title>{`Forecast ${(b.lower * 100).toFixed(0)}–${(b.upper * 100).toFixed(0)}%: ${b.unit_count} units, ${((b.observed_rate as number) * 100).toFixed(0)}% dismissed`}</title>
									</circle>
								))}
								<text
									x={PAD.l + W / 2}
									y={S - 2}
									textAnchor="middle"
									fontSize={10}
									fill="var(--ink-2)"
								>
									Forecast probability of dismissal
								</text>
							</svg>
							<dl className="mt-1 grid grid-cols-2 gap-x-2 text-xs">
								<dt className="text-ink-3">Mean forecast</dt>
								<dd className="text-right text-ink tabular">
									{(row.mean_forecast * 100).toFixed(0)}%
								</dd>
								<dt className="text-ink-3">Ranking (AUC)</dt>
								<dd className="text-right text-ink tabular">
									{row.auc.toFixed(2)}
								</dd>
							</dl>
						</div>
					);
				})}
			</div>
			<figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-3">
				<span>
					Dots: forecasts grouped in 10-point bins, sized by unit count;
					vertical position is the share actually dismissed.
				</span>
				<span>Solid diagonal: perfect calibration.</span>
				<span>Dotted line: the {(baseRate * 100).toFixed(1)}% base rate.</span>
				<span className="text-accent">
					Dashed line: the model's mean forecast.
				</span>
				<span>
					AUC 0.5 means no ranking ability; 1.0 means perfect ranking.
				</span>
			</figcaption>
		</figure>
	);
}
