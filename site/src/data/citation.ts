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

export function parseCitation(text: string): Citation {
	const cff = parse(text) as Record<string, unknown>;
	const title = str(cff.title);
	const date = str(cff["date-released"]);
	const rawAuthors = Array.isArray(cff.authors) ? cff.authors : [];
	const authors = rawAuthors.map((raw: Record<string, unknown>) => {
		const family = str(raw["family-names"]);
		const given = str(raw["given-names"]);
		if (!family || !given) {
			throw new Error("CITATION.cff: each author needs family and given names");
		}
		return { family, given, suffix: str(raw["name-suffix"]) };
	});
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

/** BibTeX `Family, Suffix, Given` form. */
const bibName = (a: CitationAuthor): string =>
	[a.family, a.suffix, a.given].filter(Boolean).join(", ");

export function toBibtex(c: Citation): string {
	const first = c.authors[0];
	const key = `${(first?.family ?? "anon").toLowerCase()}${c.year}${c.title
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "")}`;
	const fields: [string, string | null][] = [
		["author", c.authors.map(bibName).join(" and ")],
		["title", `{${c.title}}`],
		["version", c.version],
		["year", c.year],
		["date", c.date],
		["url", c.url],
	];
	const body = fields
		.filter((f): f is [string, string] => f[1] !== null)
		.map(([k, v]) => `  ${k} = {${v}},`)
		.join("\n");
	return `@software{${key},\n${body}\n}`;
}

/** APA 7 reference for software: `Family, G. G., Suffix. (Year). Title (Version v) [Computer software]. URL` */
export function toApa(c: Citation): string {
	const initials = (given: string): string =>
		given
			.split(/\s+/)
			.filter(Boolean)
			.map((part) => (part.endsWith(".") ? part : `${part[0]}.`))
			.join(" ");
	const names = c.authors.map((a) =>
		[a.family, initials(a.given), a.suffix].filter(Boolean).join(", "),
	);
	const authorList =
		names.length <= 1
			? (names[0] ?? "")
			: `${names.slice(0, -1).join(", ")}, & ${names.at(-1)}`;
	const version = c.version ? ` (Version ${c.version})` : "";
	const author = authorList.endsWith(".") ? authorList : `${authorList}.`;
	return `${author} (${c.year}). ${c.title}${version} [Computer software].${c.url ? ` ${c.url}` : ""}`;
}
