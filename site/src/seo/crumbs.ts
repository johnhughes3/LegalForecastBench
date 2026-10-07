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
	const items: Crumb[] = [{ name: "Home", path: "/" }];
	if (first === "data" && parts.length > 1) {
		items.push({ name: "Data and code", path: "/data/" });
	}
	const parent = items[items.length - 1];
	if (!parent || parent.path !== path) {
		items.push({ name: leaf, path });
	}
	return items.length >= 2 ? items : [];
}
