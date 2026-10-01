import { SITE_NAME } from "./identity.js";

/** Google's usual cutoff for the blue link. Longer titles get truncated. */
export const TITLE_LIMIT = 60;

const SEPARATOR = " · ";

/**
 * Sentence-case page title, with the site name when the pair still fits.
 * A long article title is left intact rather than cut mid-word.
 */
export function documentTitle(specific?: string): string {
	const trimmed = specific?.trim();
	if (!trimmed) return SITE_NAME;
	const branded = `${trimmed}${SEPARATOR}${SITE_NAME}`;
	return branded.length <= TITLE_LIMIT ? branded : trimmed;
}

/** Room left for a specific title once the brand suffix is attached. */
export const SPECIFIC_TITLE_LIMIT =
	TITLE_LIMIT - SEPARATOR.length - SITE_NAME.length;

export function modelTitle(displayName: string): string {
	const withResults = `${displayName} results`;
	return withResults.length <= SPECIFIC_TITLE_LIMIT ? withResults : displayName;
}
