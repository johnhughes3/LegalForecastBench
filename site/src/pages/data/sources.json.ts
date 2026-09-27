import type { APIRoute } from "astro";
import { recentResults } from "../../data/recent-results";

/** Public run links and release identity for the selected native exports. */
export const GET: APIRoute = () =>
	new Response(
		`${JSON.stringify(
			recentResults.map(({ source }) => source),
			null,
			2,
		)}\n`,
		{
			headers: { "Content-Type": "application/json" },
		},
	);
