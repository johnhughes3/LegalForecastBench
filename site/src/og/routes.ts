/**
 * Social-preview (Open Graph) image routes. The endpoint in
 * `pages/og/[...slug].png.ts` generates one PNG per key, and Layout.astro
 * falls back to `defaultOgImage` so a page never points at a missing image.
 */
export const OG_WIDTH = 1200;
export const OG_HEIGHT = 630;

export const SECTION_CARDS = {
	home: {
		eyebrow: "LegalForecastBench",
		title:
			"Can frontier models predict how federal judges rule on motions to dismiss?",
	},
	approach: {
		eyebrow: "Approach",
		title: "Law can be a verifiable domain",
	},
	experiments: {
		eyebrow: "Experiments",
		title:
			"Controlled comparisons that vary the input, harness, or reasoning setting",
	},
	findings: {
		eyebrow: "Findings",
		title: "Reports and notes on AI models and legal forecasting",
	},
	methods: {
		eyebrow: "Methods",
		title: "How the benchmark builds cases, runs models, and scores forecasts",
	},
	data: {
		eyebrow: "Data and reproduction",
		title: "Download the results and see where they come from",
	},
} as const;

export type SectionKey = keyof typeof SECTION_CARDS;

export const ogImagePath = (key: string): string => `/og/${key}.png`;

/** The section card for a route: its first path segment, or the home card. */
export function defaultOgImage(pathname: string): string {
	const segment = pathname.split("/").find(Boolean) ?? "home";
	return ogImagePath(segment in SECTION_CARDS ? segment : "home");
}
