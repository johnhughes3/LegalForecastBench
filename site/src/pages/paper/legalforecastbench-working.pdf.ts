import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { APIRoute } from "astro";

import { repositoryRoot } from "../../data/manuscript";
import { WORKING_PAPER_PDF } from "../../data/paper";

/** Same-directory full text for Scholar; the original download stays available. */
export const GET: APIRoute = () => {
	const path = resolve(repositoryRoot(), `site/public${WORKING_PAPER_PDF}`);
	if (!existsSync(path)) return new Response(null, { status: 404 });
	return new Response(new Uint8Array(readFileSync(path)), {
		headers: { "Content-Type": "application/pdf" },
	});
};
