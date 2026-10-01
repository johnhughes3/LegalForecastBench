import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { APPROACH_PUBLISHED } from "../data/approach.js";
import {
	manuscriptPath,
	parseManuscript,
	repositoryRoot,
} from "../data/manuscript.js";
import { snapshot } from "../data/results.js";

const findingsDir = resolve(repositoryRoot(), "site/src/content/findings");

function findingDates(): Map<string, string> {
	const dates = new Map<string, string>();
	for (const file of readdirSync(findingsDir)) {
		if (!file.endsWith(".md") && !file.endsWith(".mdx")) continue;
		const source = readFileSync(resolve(findingsDir, file), "utf8");
		const date = /^date:\s*(\d{4}-\d{2}-\d{2})\s*$/m.exec(source)?.[1];
		if (!date) continue;
		const id = file.replace(/\.mdx?$/, "");
		dates.set(`/findings/${id}/`, date);
	}
	return dates;
}

let cached: Map<string, string> | undefined;

/**
 * lastmod for a sitemap URL. Dates come from the snapshot, the manuscript,
 * or a finding's frontmatter. Pages without a real date are omitted.
 */
export function lastmodFor(pathname: string): string | undefined {
	if (!cached) {
		const asOf = snapshot.as_of;
		const paper = parseManuscript(
			readFileSync(manuscriptPath(), "utf8"),
		).revisedOn;
		cached = new Map<string, string>([
			["/", asOf],
			["/results/", asOf],
			["/data/", asOf],
			["/data/run-notes/", asOf],
			["/experiments/summary-pipelines/", asOf],
			["/approach/", APPROACH_PUBLISHED],
			["/methods/", asOf],
		]);
		if (paper) cached.set("/paper/", paper);
		const finding = findingDates();
		let newest = asOf;
		for (const [path, date] of finding) {
			cached.set(path, date);
			if (date > newest) newest = date;
		}
		if (APPROACH_PUBLISHED > newest) newest = APPROACH_PUBLISHED;
		cached.set("/analysis/", newest);
		for (const model of snapshot.models) {
			cached.set(`/models/${model.slug}/`, asOf);
		}
	}
	const path = pathname.endsWith("/") ? pathname : `${pathname}/`;
	return cached.get(path === "" ? "/" : path);
}
