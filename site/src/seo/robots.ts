/**
 * AI crawlers named so the policy is a decision, not a default: search
 * indexing, user-requested fetches, and model training are all allowed.
 * To opt one out, give it its own `Disallow: /` group.
 */
export const AI_CRAWLERS = [
	"GPTBot",
	"OAI-SearchBot",
	"ChatGPT-User",
	"ClaudeBot",
	"Claude-SearchBot",
	"Claude-User",
	"PerplexityBot",
	"Perplexity-User",
	"Google-Extended",
	"Applebot-Extended",
	"CCBot",
] as const;

const RULES = ["Allow: /", "Disallow: /agent/"];

/**
 * Crawlers may read the public site. The negotiation files are not a second copy.
 * A crawler obeys only its most specific group, so the named group repeats the rules.
 */
export function robotsTxt(site: URL): string {
	const sitemap = new URL("sitemap-index.xml", site).href;
	return [
		"User-agent: *",
		...RULES,
		"",
		"# AI search, assistant, and training crawlers are welcome.",
		...AI_CRAWLERS.map((agent) => `User-agent: ${agent}`),
		...RULES,
		"",
		`Sitemap: ${sitemap}`,
		"",
	].join("\n");
}
