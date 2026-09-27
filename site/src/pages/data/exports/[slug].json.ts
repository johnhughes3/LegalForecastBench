import type { APIRoute, GetStaticPaths } from "astro";
import { recentResults } from "../../../data/recent-results";
import { summaryComparisons } from "../../../data/supplementary-results";
export const getStaticPaths = (() =>
	[...recentResults, ...summaryComparisons].map(({ source, data }) => ({
		params: { slug: source.slug },
		props: { data },
	}))) satisfies GetStaticPaths;
export const GET: APIRoute = ({ props }) =>
	new Response(`${JSON.stringify(props.data, null, 2)}\n`, {
		headers: { "Content-Type": "application/json" },
	});
