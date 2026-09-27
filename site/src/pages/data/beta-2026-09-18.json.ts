import type { APIRoute } from "astro";
import { historicalSnapshot as snapshot } from "../../data/results";

/** The original September 18 snapshot, for download. */
export const GET: APIRoute = () =>
	new Response(`${JSON.stringify(snapshot, null, 2)}\n`, {
		headers: { "Content-Type": "application/json" },
	});
