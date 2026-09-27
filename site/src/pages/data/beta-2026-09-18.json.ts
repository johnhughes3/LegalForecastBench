import type { APIRoute } from "astro";
import { snapshot } from "../../data/results";

/** The exact snapshot the pages render, for download. */
export const GET: APIRoute = () =>
	new Response(`${JSON.stringify(snapshot, null, 2)}\n`, {
		headers: { "Content-Type": "application/json" },
	});
