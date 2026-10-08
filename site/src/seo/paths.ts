import { snapshot } from "../data/results.js";

export interface PublicPath {
	slug: string;
	path: string;
}

/** Canonical HTML paths that content negotiation must cover in production. */
export function publicPaths(): PublicPath[] {
	return [
		{ slug: "home", path: "/" },
		{ slug: "paper", path: "/paper/" },
		{ slug: "data", path: "/data/" },
		...snapshot.models.map((model) => ({
			slug: `models/${model.slug}`,
			path: `/models/${model.slug}/`,
		})),
	];
}
