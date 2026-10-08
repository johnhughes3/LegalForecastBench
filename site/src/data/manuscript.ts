/**
 * Read the working paper's title and abstract from the manuscript.
 *
 * The .tex file is the source of truth. The site parses it at build time so a
 * manuscript edit reaches /paper/ without a second copy in paper.ts.
 */
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MANUSCRIPT =
	"docs/papers/legalforecastbench/LegalForecastBench-paper.tex";

export interface Manuscript {
	title: string;
	abstract: readonly string[];
	/** True when the abstract still carries a drafting mark or a TODO. */
	abstractIsDraft: boolean;
	/** ISO date from `\date`, when that command contains a calendar date. */
	revisedOn: string | null;
}

const DROP_COMMANDS = new Set([
	"cite",
	"citep",
	"citet",
	"citealp",
	"label",
	"ref",
	"eqref",
	"pageref",
	"todo",
	"footnote",
	"marginpar",
]);

/**
 * Find the repository root starting from a file path.
 *
 * Astro's production build bundles this module under site/dist, so a relative
 * URL from import.meta.url no longer points at the source tree. Walk up until
 * the manuscript is present.
 */
export function repositoryRootFrom(start: string): string {
	let dir = start;
	for (let i = 0; i < 10; i += 1) {
		if (existsSync(resolve(dir, MANUSCRIPT))) return dir;
		const parent = dirname(dir);
		if (parent === dir) break;
		dir = parent;
	}
	throw new Error(`Could not find ${MANUSCRIPT} from ${start}.`);
}

export function repositoryRoot(): string {
	return repositoryRootFrom(dirname(fileURLToPath(import.meta.url)));
}

export function manuscriptPath(): string {
	return resolve(repositoryRoot(), MANUSCRIPT);
}

export function parseManuscript(source: string): Manuscript {
	const title = collapse(
		toPlain(commandArgument(stripComments(source), "title")),
	);
	const rawAbstract = environmentBody(source, "abstract");
	// Convert commands before splitting paragraphs. A drafting command can wrap
	// more than one paragraph, and splitting first would break its braces.
	const abstract = toPlain(stripComments(rawAbstract))
		.split(/\n[ \t]*\n/)
		.map((paragraph) => collapse(paragraph))
		.filter((paragraph) => paragraph.length > 0);
	if (title.length === 0) {
		throw new Error("The manuscript title is empty.");
	}
	if (abstract.length === 0) {
		throw new Error("The manuscript abstract is empty.");
	}
	return {
		title,
		abstract,
		abstractIsDraft: /\\draft\b|\\todo\b|%\s*TODO\b/.test(rawAbstract),
		revisedOn: isoDate(optionalCommandArgument(source, "date") ?? ""),
	};
}

const AI_PREPARED = /% BEGIN AI-PREPARED[\s\S]*?% END AI-PREPARED[^\n]*/g;
const SENTENCE_BREAK = /(?<=[.!?][\u201d")]?)\s+(?=[A-Z\u201c"(])/;
// A command with no argument, such as a generated number macro. The plain-text
// conversion drops it, so a passage containing one would lose words.
const BARE_COMMAND = /\\[A-Za-z]+\*?(?![A-Za-z*{[])/;

interface Paragraph {
	raw: string;
	sentences: string[];
}

/**
 * The manuscript's author-written paragraphs, in plain text. Sections marked
 * AI-PREPARED are left out, so the site cannot quote them.
 */
export function authorParagraphs(source: string): Paragraph[] {
	const begin = source.indexOf("\\begin{document}");
	const end = source.indexOf("\\begin{thebibliography}");
	if (begin < 0 || end < 0) {
		throw new Error("The manuscript is missing its document body.");
	}
	const body = stripComments(
		source.slice(begin, end).replace(AI_PREPARED, "\n\n"),
	).replace(/\\(?:begin|end)\{[^}]*\}|\\(?:sub)*section\*?\{[^}]*\}/g, "\n\n");
	const paragraphs: Paragraph[] = [];
	for (const raw of body.split(/\n[ \t]*\n/)) {
		let plain: string;
		try {
			plain = collapse(toPlain(raw));
		} catch {
			continue; // A drafting command spanning paragraphs; never quoted.
		}
		if (plain) paragraphs.push({ raw, sentences: plain.split(SENTENCE_BREAK) });
	}
	return paragraphs;
}

/**
 * Quote the paper verbatim: `count` sentences (default: the rest of the
 * paragraph) starting with the sentence that opens with `opening`. Fails the
 * build when the opening is missing, ambiguous, or in an AI-prepared section,
 * so the site never drifts from the paper unnoticed.
 */
export function quoteFrom(
	paragraphs: readonly Paragraph[],
	opening: string,
	count?: number,
): string {
	const hits = paragraphs.flatMap((paragraph) => {
		const start = paragraph.sentences.findIndex((s) => s.startsWith(opening));
		return start < 0 ? [] : [{ paragraph, start }];
	});
	const hit = hits[0];
	if (!hit || hits.length > 1) {
		throw new Error(
			`Expected one author-written passage opening "${opening}" in the manuscript; found ${hits.length}.`,
		);
	}
	const bare = BARE_COMMAND.exec(hit.paragraph.raw);
	if (bare) {
		throw new Error(
			`The passage opening "${opening}" uses ${bare[0]}, which plain text would drop.`,
		);
	}
	const end = count === undefined ? undefined : hit.start + count;
	return hit.paragraph.sentences.slice(hit.start, end).join(" ");
}

function stripComments(source: string): string {
	return source
		.split("\n")
		.map((line) => {
			let kept = "";
			for (let i = 0; i < line.length; i += 1) {
				if (line[i] === "%" && line[i - 1] !== "\\") break;
				kept += line[i];
			}
			return kept;
		})
		.join("\n");
}

const MONTHS = [
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
] as const;

/** Pull `Month D, YYYY` out of a manuscript date command. */
function isoDate(text: string): string | null {
	const match =
		/\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(\d{4})\b/.exec(
			text,
		);
	if (!match) return null;
	const month = String(
		MONTHS.indexOf(match[1] as (typeof MONTHS)[number]) + 1,
	).padStart(2, "0");
	const day = match[2]?.padStart(2, "0");
	return `${match[3]}-${month}-${day}`;
}

function optionalCommandArgument(source: string, name: string): string | null {
	const match = new RegExp(`\\\\${name}\\*?(?:\\[[^\\]]*\\])?\\{`).exec(source);
	if (!match) return null;
	return balanced(source, match.index + match[0].length - 1).inner;
}

function commandArgument(source: string, name: string): string {
	const argument = optionalCommandArgument(source, name);
	if (argument === null) {
		throw new Error(`The manuscript is missing \\${name}.`);
	}
	return argument;
}

function environmentBody(source: string, name: string): string {
	const begin = `\\begin{${name}}`;
	const end = `\\end{${name}}`;
	const start = source.indexOf(begin);
	const finish = source.indexOf(end, start + begin.length);
	if (start < 0 || finish < 0) {
		throw new Error(`The manuscript is missing the ${name} environment.`);
	}
	return source.slice(start + begin.length, finish);
}

/** Read a `{...}` group. `openBrace` points at the opening brace. */
function balanced(
	source: string,
	openBrace: number,
): { inner: string; next: number } {
	let depth = 0;
	let i = openBrace;
	const start = openBrace + 1;
	while (i < source.length) {
		if (source[i] === "\\") {
			i += 2;
			continue;
		}
		if (source[i] === "{") depth += 1;
		else if (source[i] === "}") {
			depth -= 1;
			if (depth === 0) {
				return { inner: source.slice(start, i), next: i + 1 };
			}
		}
		i += 1;
	}
	throw new Error("The manuscript has an unclosed brace.");
}

function toPlain(input: string): string {
	let out = "";
	let i = 0;
	while (i < input.length) {
		if (input.startsWith("---", i)) {
			out += "—";
			i += 3;
			continue;
		}
		if (input.startsWith("--", i)) {
			out += "–";
			i += 2;
			continue;
		}
		// TeX double quotes. Left raw, they reach the page and its metadata as backticks.
		if (input.startsWith("``", i)) {
			out += "\u201c";
			i += 2;
			continue;
		}
		if (input.startsWith("''", i)) {
			out += "\u201d";
			i += 2;
			continue;
		}
		const ch = input[i] ?? "";
		if (ch === "~") {
			out += " ";
			i += 1;
			continue;
		}
		if (ch === "{" || ch === "}") {
			i += 1;
			continue;
		}
		if (ch !== "\\") {
			out += ch;
			i += 1;
			continue;
		}
		i += 1;
		const escaped = input[i] ?? "";
		if (escaped === "\\") {
			out += " ";
			i += 1;
			continue;
		}
		if ("$%&#_{}".includes(escaped)) {
			out += escaped;
			i += 1;
			continue;
		}
		if (escaped === "," || escaped === " ") {
			out += " ";
			i += 1;
			continue;
		}
		if (!/[A-Za-z]/.test(escaped)) {
			out += escaped;
			i += 1;
			continue;
		}
		const nameStart = i;
		while (i < input.length && /[A-Za-z]/.test(input[i] ?? "")) i += 1;
		const name = input.slice(nameStart, i);
		if (input[i] === "*") i += 1;
		if (input[i] === "[") {
			const close = input.indexOf("]", i + 1);
			i = close === -1 ? input.length : close + 1;
		}
		if (input[i] !== "{") continue;
		const group = balanced(input, i);
		i = group.next;
		// \href{url}{text}: keep the text, which follows as an ordinary group.
		if (name === "href") continue;
		if (!DROP_COMMANDS.has(name)) out += toPlain(group.inner);
	}
	return out;
}

function collapse(text: string): string {
	return text
		.replace(/\s+/g, " ")
		.replace(/\s+([.,;:])/g, "$1")
		.trim();
}
