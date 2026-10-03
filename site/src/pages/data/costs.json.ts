import type { APIRoute } from "astro";
import { datasetJson } from "../../data/dataset-input.js";
import costs from "../../data/receipt-costs.json";

export const GET: APIRoute = () =>
	new Response(
		`${JSON.stringify(datasetJson("costs.json", costs), null, 2)}\n`,
		{
			headers: { "Content-Type": "application/json" },
		},
	);
