/**
 * Accept-header test for markdown negotiation.
 *
 * Matches `text/markdown` or `text/plain` only when that token is not preceded
 * by `text/html`, so a browser that lists markdown after HTML still gets HTML.
 * The leading `^` keeps the check on the whole header: an unanchored search
 * can succeed on the markdown token alone and ignore an earlier `text/html`.
 * Adapted from vercel-labs/markdown-for-agents.
 */
export const ACCEPT_MARKDOWN_PATTERN =
	"^(?=.*(?:text/plain|text/markdown))(?!.*text/html.*(?:text/plain|text/markdown)).*";

const ACCEPT_MARKDOWN = new RegExp(ACCEPT_MARKDOWN_PATTERN);

export function prefersMarkdown(accept: string | null | undefined): boolean {
	if (!accept) return false;
	return ACCEPT_MARKDOWN.test(accept);
}
