import type { APIRoute } from "astro";

/** Allow crawling and point to the generated sitemap on the configured site. */
export const GET: APIRoute = ({ site }) => {
	const sitemap = new URL("sitemap-index.xml", site).toString();
	return new Response(`User-agent: *\nAllow: /\n\nSitemap: ${sitemap}\n`, {
		headers: { "Content-Type": "text/plain; charset=utf-8" },
	});
};
