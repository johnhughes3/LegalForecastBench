import { type RefObject, useEffect, useRef, useState } from "react";

/** Track an element's rendered width so SVG text stays legible at every size. */
export function useWidth<T extends HTMLElement>(
	initial: number,
): [RefObject<T | null>, number] {
	const ref = useRef<T>(null);
	const [width, setWidth] = useState(initial);
	useEffect(() => {
		const node = ref.current;
		if (!node) return;
		const observer = new ResizeObserver(([entry]) => {
			if (entry) setWidth(Math.round(entry.contentRect.width));
		});
		observer.observe(node);
		return () => observer.disconnect();
	}, []);
	return [ref, width];
}
