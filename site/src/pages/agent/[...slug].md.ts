import type { APIRoute, GetStaticPaths } from "astro";

import { agentDocuments } from "../../seo/documents";

export const getStaticPaths = (async () => {
	const docs = await agentDocuments();
	return docs.map((doc) => ({
		params: { slug: doc.slug },
		props: { markdown: doc.markdown },
	}));
}) satisfies GetStaticPaths;

export const GET: APIRoute = ({ props }) => {
	const { markdown } = props as { markdown: string };
	return new Response(markdown, {
		headers: {
			"Content-Type": "text/markdown; charset=utf-8",
			"Cache-Control": "public, max-age=3600, s-maxage=86400",
			"X-Robots-Tag": "noindex, nofollow",
		},
	});
};
