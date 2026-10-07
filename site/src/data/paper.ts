/**
 * The working paper, as listed on /paper/ and linked from every page.
 *
 * Title and abstract come from the manuscript, so they cannot drift from it.
 * The citation and the first-publication date come from the
 * `preferred-citation` block of CITATION.cff. The website serves one
 * replaceable working PDF. To publish an immutable version, add a new file
 * under public/paper/, append a row to `versions`, and leave the older file
 * in place.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { parsePaperCitation } from "./citation.js";
import {
	manuscriptPath,
	parseManuscript,
	repositoryRoot,
} from "./manuscript.js";

const manuscript = parseManuscript(readFileSync(manuscriptPath(), "utf8"));

/** How to cite the paper. CITATION.cff is the only place this is written. */
export const PAPER_CITATION = parsePaperCitation(
	readFileSync(resolve(repositoryRoot(), "CITATION.cff"), "utf8"),
);

export interface PaperVersion {
	version: string;
	/** ISO date the version was posted. */
	date: string;
	/** Site path of the immutable PDF, e.g. /paper/legalforecastbench-v0.1.pdf. */
	pdf: string;
	/** The results release the version analyzes. */
	release: string;
	/** What changed from the prior version; omit for the first. */
	changes?: string;
}

/**
 * The one URL of the PDF rebuilt from the current manuscript. It sits beside
 * the abstract page because Google Scholar requires that of the full text.
 * `vercel.json` redirects the earlier /papers/ path here.
 */
export const WORKING_PAPER_PDF = "/paper/legalforecastbench-working.pdf";

export const PAPER = {
	title: manuscript.title,
	author: "John J. Hughes, III",
	status: "Working paper" as const,
	abstract: manuscript.abstract,
	abstractIsDraft: manuscript.abstractIsDraft,
	/** ISO date of first publication. Manuscript edits do not move it. */
	publishedOn: PAPER_CITATION.date,
	/** ISO date from the manuscript `\date`, or null when it has none. */
	revisedOn: manuscript.revisedOn,
	workingPdf: WORKING_PAPER_PDF,
	versions: [] as PaperVersion[],
};

/** The newest immutable version, or null before the first one is released. */
export const currentPaper: PaperVersion | null = PAPER.versions.at(-1) ?? null;
