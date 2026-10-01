import type { SitemapItem } from "@astrojs/sitemap";

import { lastmodFor } from "./lastmod.js";

/** HTML pages only. Agent markdown, images, and data files stay out. */
export function includeInSitemap(pageUrl: string): boolean {
	const path = new URL(pageUrl).pathname;
	if (path.startsWith("/agent")) return false;
	if (path.startsWith("/og/")) return false;
	if (path.includes("404")) return false;
	if (/\.[a-z0-9]+$/i.test(path)) return false;
	return true;
}

export function withLastmod(item: SitemapItem): SitemapItem {
	const lastmod = lastmodFor(new URL(item.url).pathname);
	return lastmod ? { url: item.url, lastmod } : { url: item.url };
}
