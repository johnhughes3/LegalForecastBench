import { parse } from "yaml";

/** The subset of CITATION.cff (Citation File Format 1.2) the site renders. */
export interface Citation {
	title: string;
	version: string | null;
	year: string;
	date: string | null;
	url: string | null;
	authors: CitationAuthor[];
}

export interface CitationAuthor {
	family: string;
	given: string;
	suffix: string | null;
}

const str = (value: unknown): string | null =>
	value instanceof Date
		? value.toISOString().slice(0, 10)
		: typeof value === "string" || typeof value === "number"
			? String(value)
			: null;

function parseAuthors(raw: unknown): CitationAuthor[] {
	const rawAuthors = Array.isArray(raw) ? raw : [];
	return rawAuthors.map((author: Record<string, unknown>) => {
		const family = str(author["family-names"]);
		const given = str(author["given-names"]);
		if (!family || !given) {
			throw new Error("CITATION.cff: each author needs family and given names");
		}
		return { family, given, suffix: str(author["name-suffix"]) };
	});
}

export function parseCitation(text: string): Citation {
	const cff = parse(text) as Record<string, unknown>;
	const title = str(cff.title);
	const date = str(cff["date-released"]);
	const authors = parseAuthors(cff.authors);
	if (!title || !date || authors.length === 0) {
		throw new Error(
			"CITATION.cff must declare title, date-released, and authors",
		);
	}
	return {
		title,
		version: str(cff.version),
		year: date.slice(0, 4),
		date,
		url: str(cff.url) ?? str(cff["repository-code"]),
		authors,
	};
}

/** The `preferred-citation` block of CITATION.cff: the working paper. */
export interface PaperCitation {
	title: string;
	year: string;
	/** ISO date of first publication. Manuscript edits do not move it. */
	date: string;
	url: string;
	/** Absent until the paper has one. */
	doi: string | null;
	note: string | null;
	authors: CitationAuthor[];
}

export function parsePaperCitation(text: string): PaperCitation {
	const cff = parse(text) as Record<string, unknown>;
	const paper = (cff["preferred-citation"] ?? {}) as Record<string, unknown>;
	const title = str(paper.title);
	const date = str(paper["date-published"]);
	const url = str(paper.url);
	const authors = parseAuthors(paper.authors);
	if (!title || !date || !url || authors.length === 0) {
		throw new Error(
			"CITATION.cff preferred-citation must declare title, date-published, url, and authors",
		);
	}
	// GitHub's citation widget reads year and month, not date-published.
	const month = String(Number(date.slice(5, 7)));
	if (str(paper.year) !== date.slice(0, 4) || str(paper.month) !== month) {
		throw new Error(
			"CITATION.cff preferred-citation: year and month must match date-published",
		);
	}
	return {
		title,
		year: date.slice(0, 4),
		date,
		url,
		doi: str(paper.doi),
		note: str(paper.notes),
		authors,
	};
}

/** BibTeX `Family, Suffix, Given` form. */
const bibName = (a: CitationAuthor): string =>
	[a.family, a.suffix, a.given].filter(Boolean).join(", ");

function bibEntry(
	type: string,
	key: string,
	fields: [string, string | null][],
): string {
	const body = fields
		.filter((f): f is [string, string] => f[1] !== null)
		.map(([k, v]) => `  ${k} = {${v}},`)
		.join("\n");
	return `@${type}{${key},\n${body}\n}`;
}

const slug = (text: string): string =>
	text.toLowerCase().replace(/[^a-z0-9]+/g, "");

export function toBibtex(c: Citation): string {
	const first = c.authors[0];
	const key = `${slug(first?.family ?? "anon")}${c.year}${slug(c.title)}`;
	return bibEntry("software", key, [
		["author", c.authors.map(bibName).join(" and ")],
		["title", `{${c.title}}`],
		["version", c.version],
		["year", c.year],
		["date", c.date],
		["url", c.url],
	]);
}

/** `@misc` until the paper has a venue. The key is the title's first word. */
export function toPaperBibtex(c: PaperCitation): string {
	const first = c.authors[0];
	const word = c.title.split(/[^A-Za-z0-9]/)[0] ?? "";
	const key = `${slug(first?.family ?? "anon")}${c.year}${slug(word)}`;
	return bibEntry("misc", key, [
		["author", c.authors.map(bibName).join(" and ")],
		["title", `{${c.title}}`],
		["year", c.year],
		["date", c.date],
		["note", c.note],
		["doi", c.doi],
		["url", c.url],
	]);
}

/** APA 7 reference for software: `Family, G. G., Suffix. (Year). Title (Version v) [Computer software]. URL` */
export function toApa(c: Citation): string {
	const version = c.version ? ` (Version ${c.version})` : "";
	return `${apaAuthors(c.authors)} (${c.year}). ${c.title}${version} [Computer software].${c.url ? ` ${c.url}` : ""}`;
}

/** APA 7 reference for an unpublished paper; a DOI replaces the URL. */
export function toPaperApa(c: PaperCitation): string {
	const note = c.note ? ` [${c.note}]` : "";
	const link = c.doi ? `https://doi.org/${c.doi}` : c.url;
	return `${apaAuthors(c.authors)} (${c.year}). ${c.title}${note}. ${link}`;
}

function apaAuthors(authors: readonly CitationAuthor[]): string {
	const initials = (given: string): string =>
		given
			.split(/\s+/)
			.filter(Boolean)
			.map((part) => (part.endsWith(".") ? part : `${part[0]}.`))
			.join(" ");
	const names = authors.map((a) =>
		[a.family, initials(a.given), a.suffix].filter(Boolean).join(", "),
	);
	const list =
		names.length <= 1
			? (names[0] ?? "")
			: `${names.slice(0, -1).join(", ")}, & ${names.at(-1)}`;
	return list.endsWith(".") ? list : `${list}.`;
}
