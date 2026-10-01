import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { repositoryRoot } from "../data/manuscript.js";
import { snapshot } from "../data/results.js";

const findingsDir = resolve(repositoryRoot(), "site/src/content/findings");

export interface PublicPath {
	slug: string;
	path: string;
}

function publishedFindingIds(): string[] {
	const ids: string[] = [];
	for (const file of readdirSync(findingsDir)) {
		if (!file.endsWith(".md") && !file.endsWith(".mdx")) continue;
		const source = readFileSync(resolve(findingsDir, file), "utf8");
		const frontmatter = /^---\r?\n([\s\S]*?)\r?\n---/.exec(source)?.[1] ?? "";
		if (/^draft:\s*true\s*$/m.test(frontmatter)) continue;
		ids.push(file.replace(/\.mdx?$/, ""));
	}
	return ids;
}

/** Canonical HTML paths that content negotiation must cover in production. */
export function publicPaths(): PublicPath[] {
	const staticPaths: PublicPath[] = [
		{ slug: "home", path: "/" },
		{ slug: "results", path: "/results/" },
		{ slug: "methods", path: "/methods/" },
		{ slug: "paper", path: "/paper/" },
		{ slug: "analysis", path: "/analysis/" },
		{ slug: "approach", path: "/approach/" },
		{
			slug: "experiments/summary-pipelines",
			path: "/experiments/summary-pipelines/",
		},
		{ slug: "data", path: "/data/" },
		{ slug: "data/run-notes", path: "/data/run-notes/" },
	];
	return [
		...staticPaths,
		...snapshot.models.map((model) => ({
			slug: `models/${model.slug}`,
			path: `/models/${model.slug}/`,
		})),
		...publishedFindingIds().map((id) => ({
			slug: `findings/${id}`,
			path: `/findings/${id}/`,
		})),
	];
}
