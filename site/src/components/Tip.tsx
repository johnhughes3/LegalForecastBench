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

/**
 * Shared document handlers serve static Astro roots and hydrated islands.
 * Native popovers escape table overflow without moving React-owned DOM nodes.
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
		<span
			data-tip
			data-side={side}
			data-align={align}
			className={`inline-flex ${className}`}
		>
			{focusable ? (
				<button
					type="button"
					aria-describedby={id}
					className="inline-flex cursor-help appearance-none rounded-full border-0 bg-transparent p-0 text-left font-[inherit] text-inherit"
				>
					{children}
				</button>
			) : isValidElement(children) ? (
				// Describe the child itself (e.g. a sort button) so the focused
				// control announces the explanation.
				cloneElement(
					children as ReactElement<{ "aria-describedby"?: string }>,
					{
						"aria-describedby": id,
					},
				)
			) : (
				<span aria-describedby={id} className="inline-flex">
					{children}
				</span>
			)}
			<span
				role="tooltip"
				id={id}
				popover="manual"
				className="tip-content rounded-lg border border-rule bg-surface px-3 py-2 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-ink-2 shadow-lg"
			>
				{tip}
			</span>
		</span>
	);
}
