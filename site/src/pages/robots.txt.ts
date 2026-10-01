import type { APIRoute } from "astro";

import { robotsTxt } from "../seo/robots";

export const GET: APIRoute = ({ site }) => {
	if (!site) throw new Error("site is not configured");
	return new Response(robotsTxt(site), {
		headers: { "Content-Type": "text/plain; charset=utf-8" },
	});
};
