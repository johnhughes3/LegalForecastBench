import type { APIRoute } from "astro";

import { agentDocuments, llmsTxt } from "../seo/documents";

export const GET: APIRoute = async () => {
	const body = llmsTxt(agentDocuments());
	return new Response(body, {
		headers: {
			"Content-Type": "text/plain; charset=utf-8",
			"Cache-Control": "public, max-age=3600, s-maxage=86400",
		},
	});
};
