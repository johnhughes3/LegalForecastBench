import { EXPLAIN } from "../data/explanations";
import type { Eligibility } from "../data/snapshot";
import Tip from "./Tip";

const LABEL: Record<Eligibility, string> = {
	eligible: "Eligible",
	qualified: "Qualified",
	unknown: "Unknown",
};

/** Status is carried by icon and label, never color alone. */
export default function EligibilityBadge({
	eligibility,
	reason,
	side = "top",
	align = "center",
}: {
	eligibility: Eligibility;
	reason: string;
	side?: "top" | "bottom";
	align?: "center" | "start" | "end";
}) {
	const eligible = eligibility === "eligible";
	const tip = (
		<>
			<span className="block">
				{EXPLAIN[eligibility]}
			</span>
			<span className="mt-1.5 block font-medium text-ink">{reason}</span>
		</>
	);
	return (
		<Tip tip={tip} side={side} align={align}>
			<span
				className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${
					eligible
						? "border-good/30 text-good"
						: "border-rule-strong text-ink-3"
				}`}
			>
				{eligible ? (
					<svg className="size-3" viewBox="0 0 12 12" aria-hidden="true">
						<path
							d="M2.5 6.2 5 8.5l4.5-5"
							fill="none"
							stroke="currentColor"
							strokeWidth="1.6"
							strokeLinecap="round"
						/>
					</svg>
				) : (
					<svg className="size-3" viewBox="0 0 12 12" aria-hidden="true">
						<circle
							cx="6"
							cy="6"
							r="4.2"
							fill="none"
							stroke="currentColor"
							strokeWidth="1.3"
						/>
						<path
							d="M6 3.8v2.6M6 8.1v.1"
							stroke="currentColor"
							strokeWidth="1.4"
							strokeLinecap="round"
						/>
					</svg>
				)}
				{LABEL[eligibility]}
			</span>
		</Tip>
	);
}
