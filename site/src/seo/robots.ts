/** Crawlers may read the public site. The negotiation files are not a second copy. */
export function robotsTxt(site: URL): string {
	const sitemap = new URL("sitemap-index.xml", site).href;
	return `User-agent: *\nAllow: /\nDisallow: /agent/\n\nSitemap: ${sitemap}\n`;
}
