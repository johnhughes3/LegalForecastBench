import type { Crumb } from "./jsonld.js";

/**
 * Breadcrumb trail from the URL. The layout renders the same items, so the
 * BreadcrumbList matches the visible trail. The homepage has no trail.
 */
export function crumbsFor(pathname: string, leaf: string): Crumb[] {
	const path =
		pathname === "/" ? "/" : pathname.endsWith("/") ? pathname : `${pathname}/`;
	if (path === "/" || path === "/404/") return [];
	const parts = path.split("/").filter(Boolean);
	const first = parts[0];
	const items: Crumb[] = [{ name: "Overview", path: "/" }];
	if (first === "models") {
		items.push({ name: "Results", path: "/results/" });
	} else if (
		first === "findings" ||
		first === "experiments" ||
		first === "approach"
	) {
		items.push({ name: "Analysis", path: "/analysis/" });
	} else if (first === "lab") {
		items.push({ name: "Analysis", path: "/analysis/" });
		if (parts.length > 1) items.push({ name: "LAB explorer", path: "/lab/" });
	} else if (first === "data" && parts.length > 1) {
		items.push({ name: "Data and code", path: "/data/" });
	}
	const parent = items[items.length - 1];
	if (!parent || parent.path !== path) {
		items.push({ name: leaf, path });
	}
	return items.length >= 2 ? items : [];
}
