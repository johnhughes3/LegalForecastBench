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
	paper: {
		eyebrow: "Working paper",
		title: "Forecasting judicial decisions as a test of legal reasoning",
	},
	data: {
		eyebrow: "Data & code",
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
