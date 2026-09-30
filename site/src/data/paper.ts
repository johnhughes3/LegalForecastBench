/**
 * The working paper, as listed on /paper/ and linked from every page.
 *
 * Title and abstract come from the manuscript, so they cannot drift from it.
 * The website serves one replaceable working PDF. To publish an immutable
 * version, add a new file under public/papers/, append a row to `versions`,
 * and leave the older file in place.
 */
import { readFileSync } from "node:fs";

import { manuscriptPath, parseManuscript } from "./manuscript.js";

const manuscript = parseManuscript(readFileSync(manuscriptPath(), "utf8"));

export interface PaperVersion {
	version: string;
	/** ISO date the version was posted. */
	date: string;
	/** Site path of the immutable PDF, e.g. /papers/legalforecastbench-v0.1.pdf. */
	pdf: string;
	/** The results release the version analyzes. */
	release: string;
	/** What changed from the prior version; omit for the first. */
	changes?: string;
}

/** Stable URL of the PDF rebuilt from the current manuscript. */
export const WORKING_PAPER_PDF = "/papers/legalforecastbench-working.pdf";

export const PAPER = {
	title: manuscript.title,
	author: "John J. Hughes, III",
	status: "Working paper" as const,
	abstract: manuscript.abstract,
	abstractIsDraft: manuscript.abstractIsDraft,
	workingPdf: WORKING_PAPER_PDF,
	versions: [] as PaperVersion[],
};

/** The newest immutable version, or null before the first one is released. */
export const currentPaper: PaperVersion | null = PAPER.versions.at(-1) ?? null;
