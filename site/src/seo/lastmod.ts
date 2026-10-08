import { readFileSync } from "node:fs";

import { manuscriptPath, parseManuscript } from "../data/manuscript.js";
import { snapshot } from "../data/results.js";

let cached: Map<string, string> | undefined;

/**
 * lastmod for a sitemap URL. Dates come from the snapshot or the manuscript.
 * Pages without a real date are omitted.
 */
export function lastmodFor(pathname: string): string | undefined {
	if (!cached) {
		const asOf = snapshot.as_of;
		const paper = parseManuscript(
			readFileSync(manuscriptPath(), "utf8"),
		).revisedOn;
		cached = new Map<string, string>([
			["/", asOf],
			["/data/", asOf],
		]);
		if (paper) cached.set("/paper/", paper);
		for (const model of snapshot.models) {
			cached.set(`/models/${model.slug}/`, asOf);
		}
	}
	const path = pathname.endsWith("/") ? pathname : `${pathname}/`;
	return cached.get(path === "" ? "/" : path);
}
