/**
 * Prose the site quotes from the working paper, verbatim.
 *
 * The paper owns interpretation; the site repeats the author's own sentences
 * rather than paraphrasing them. Each passage is found by its opening words in
 * the manuscript at build time, outside the AI-prepared sections, so an edit to
 * the paper either flows through here or fails the build.
 */
import { readFileSync } from "node:fs";
import { authorParagraphs, manuscriptPath, quoteFrom } from "./manuscript.js";

const paragraphs = authorParagraphs(readFileSync(manuscriptPath(), "utf8"));
const quote = (opening: string, count?: number): string =>
	quoteFrom(paragraphs, opening, count);

export const PAPER_PROSE = {
	/** Abstract: the cohort and the headline result. */
	headline: quote("The beta includes", 2),
	/** Disclosure: where the code and documents are. */
	access: quote("Code is maintained in the"),
	/** Disclosure: the invitation for feedback. */
	feedback: quote("This version of the paper is intended", 1),
} as const;
