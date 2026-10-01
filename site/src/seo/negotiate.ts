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
 * Header rewrites for the canonical URL. Destinations live under `/agent/`
 * and are disallowed in robots.txt. They are not linked or sitemapped.
 *
 * Vercel compiles `source` with path-to-regexp, which rejects `?` (`/?` is
 * read as a modifier, not an optional slash). These patterns use the trailing
 * slash the site already canonicalizes, anchored so `/data/` does not swallow
 * `/data/current.json`.
 */
export function negotiationRewrites(): NegotiationRewrite[] {
	return [
		{ source: "/", has: HAS, destination: "/agent/home.md" },
		{
			source: "^/(results|methods|paper|analysis|approach)/$",
			has: HAS,
			destination: "/agent/$1.md",
		},
		{ source: "^/data/$", has: HAS, destination: "/agent/data.md" },
		{
			source: "^/data/run-notes/$",
			has: HAS,
			destination: "/agent/data/run-notes.md",
		},
		{
			source: "^/(models|findings|experiments)/([^/]+)/$",
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
