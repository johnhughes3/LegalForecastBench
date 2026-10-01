import { AUTHOR, REPO } from "../data/author.js";

/** Public origin. `astro.config` and every absolute URL on the site read this. */
export const SITE_ORIGIN = (
	process.env.SITE_URL ?? "https://www.legalforecastbench.org"
).replace(/\/$/, "");

export const SITE_NAME = "LegalForecastBench";

export const SITE_DESCRIPTION =
	"An open research benchmark testing whether AI models can forecast federal motion-to-dismiss outcomes from the court record available before the decision.";

/** Raster-free mark that already ships in `public/`. */
export const LOGO_PATH = "/favicon.svg";

export function originUrl(): URL {
	return new URL(`${SITE_ORIGIN}/`);
}

export function absoluteUrl(path: string): string {
	return new URL(path, originUrl()).href;
}

export const organizationId = `${SITE_ORIGIN}/#organization`;
export const websiteId = `${SITE_ORIGIN}/#website`;
export const authorId = `${SITE_ORIGIN}/#author`;

export { AUTHOR, REPO };
