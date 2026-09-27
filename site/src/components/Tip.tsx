import {
	cloneElement,
	isValidElement,
	type ReactElement,
	type ReactNode,
	useId,
} from "react";

interface Props {
	/** Explanation shown on hover, keyboard focus, or tap. */
	tip: ReactNode;
	children: ReactNode;
	side?: "top" | "bottom";
	align?: "center" | "start" | "end";
	/**
	 * Make the trigger focusable. Turn off when the child is already a button
	 * or link, so keyboard users do not get two tab stops.
	 */
	focusable?: boolean;
	className?: string;
}

const SIDE = { top: "bottom-full mb-2", bottom: "top-full mt-2" };
const ALIGN = {
	center: "left-1/2 -translate-x-1/2",
	start: "left-0",
	end: "right-0",
};

/**
 * CSS-only tooltip: works on static pages and inside hydrated islands, opens
 * on hover and focus (a tap focuses it on touch screens), and is announced to
 * screen readers through aria-describedby.
 */
export default function Tip({
	tip,
	children,
	side = "top",
	align = "center",
	focusable = true,
	className = "",
}: Props) {
	const id = useId();
	return (
		<span className={`group/tip relative inline-flex ${className}`}>
			{focusable ? (
				<button
					type="button"
					aria-describedby={id}
					className="inline-flex cursor-help appearance-none rounded-full border-0 bg-transparent p-0 text-left font-[inherit] text-inherit outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
				>
					{children}
				</button>
			) : isValidElement(children) ? (
				// Describe the child itself (e.g. a sort button) so the focused
				// control announces the explanation.
				cloneElement(children as ReactElement<{ "aria-describedby"?: string }>, {
					"aria-describedby": id,
				})
			) : (
				<span aria-describedby={id} className="inline-flex">
					{children}
				</span>
			)}
			<span
				role="tooltip"
				id={id}
				className={`pointer-events-none invisible absolute z-40 w-64 max-w-[80vw] rounded-lg border border-rule bg-surface px-3 py-2 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-ink-2 opacity-0 shadow-lg transition-opacity duration-150 group-focus-within/tip:visible [.tips-dismissed_&]:invisible! [.tips-dismissed_&]:opacity-0! group-focus-within/tip:opacity-100 group-hover/tip:visible group-hover/tip:opacity-100 ${SIDE[side]} ${ALIGN[align]}`}
			>
				{tip}
			</span>
		</span>
	);
}
