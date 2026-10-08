import type { APIRoute } from "astro";
import { buildIndex } from "../../../lab/index-format";
import { loadLab } from "../../../lab/load";

/** Compact one-row-per-criterion index for the Full runs scanner. */
export const GET: APIRoute = () =>
	new Response(JSON.stringify(buildIndex(loadLab())), {
		headers: { "Content-Type": "application/json" },
	});
