import { ACCEPT_MARKDOWN_PATTERN, prefersMarkdown } from "./accept.js";

export interface NegotiationRewrite {
	source: string;
	has: { type: "header"; key: "accept"; value: string }[];
	destination: string;
}

const HAS = [
	{
		type: "header" as const,
		key: "accept" as const,
		value: ACCEPT_MARKDOWN_PATTERN,
	},
];

/**
 * Header rewrites for the canonical URL, kept for a tested follow-up.
 *
 * As deployed they do not fire. Vercel gives the filesystem precedence over
 * `rewrites`, and every page here is a static file. The `^` and `$` in these
 * sources are also read as literal characters. Until that is fixed and
 * checked against a live deployment, agents reach the markdown copies by
 * their own URLs: llms.txt links them and each page names its copy in a
 * `<link rel="alternate" type="text/markdown">`, via `markdownDestination`.
 *
 * Vercel compiles `source` with path-to-regexp, which rejects `?` (`/?` is
 * read as a modifier, not an optional slash). These patterns use the trailing
 * slash the site already canonicalizes, anchored so `/data/` does not swallow
 * `/data/current.json`.
 */
export function negotiationRewrites(): NegotiationRewrite[] {
	return [
		{ source: "/", has: HAS, destination: "/agent/home.md" },
		{ source: "^/(paper|data)/$", has: HAS, destination: "/agent/$1.md" },
		{
			source: "^/(models)/([^/]+)/$",
			has: HAS,
			destination: "/agent/$1/$2.md",
		},
	];
}

/** Where an Accept-negotiated request for `pathname` should be served from. */
export function markdownDestination(
	pathname: string,
	accept: string | null | undefined,
): string | null {
	if (!prefersMarkdown(accept)) return null;
	for (const rule of negotiationRewrites()) {
		if (rule.source === "/") {
			if (pathname === "/" || pathname === "") return rule.destination;
			continue;
		}
		const match = new RegExp(rule.source).exec(pathname);
		if (!match) continue;
		return rule.destination.replace(/\$(\d+)/g, (_, group: string) => {
			return match[Number(group)] ?? "";
		});
	}
	return null;
}
