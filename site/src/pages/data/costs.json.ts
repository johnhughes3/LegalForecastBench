import type { APIRoute } from "astro";
import costs from "../../data/receipt-costs.json";

export const GET: APIRoute = () =>
	new Response(`${JSON.stringify(costs, null, 2)}\n`, {
		headers: { "Content-Type": "application/json" },
	});
