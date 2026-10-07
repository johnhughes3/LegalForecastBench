/** Author and project links shared by the header, footer, homepage, and paper page. */
export const AUTHOR = {
	name: "John J. Hughes, III",
	/** The form his own site uses. Both must resolve to one person. */
	alternateName: "John J. Hughes III",
	/**
	 * `Family Suffix, Given` for bibliographic tags. Google Scholar reads a
	 * comma as "Last, First", so the display name would index "III" as the
	 * given name.
	 */
	citationName: "Hughes III, John J.",
	site: "https://www.johnjhughesiii.com/",
	research: "https://www.johnjhughesiii.com/research/",
	contact: "https://www.johnjhughesiii.com/contact/",
	github: "https://github.com/johnhughes3",
	linkedin: "https://www.linkedin.com/in/jhughes3",
	x: "https://x.com/jjhughes3",
	xHandle: "@jjhughes3",
} as const;

/** The research community the author belongs to. Not a scholarly affiliation. */
export const LEGALQUANTS = {
	name: "LegalQuants",
	url: "https://www.legalquants.com/",
} as const;

export const REPO = "https://github.com/johnhughes3/LegalForecastBench";
