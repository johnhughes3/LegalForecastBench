/**
 * Parse the reviewer's worksheet (docs/.../human-review/worksheet.md).
 *
 * The worksheet is the source of truth: the explorer reads the reviewer's
 * verdicts from it at build time and never keeps a second copy. The patterns
 * mirror `scripts/harvey_review_sample.py` (`parse_worksheet`,
 * `environment_verdicts`, `objective_errors`), which the Python tally uses.
 */
import type {
	AiReasoning,
	EnvironmentVerdict,
	ReviewItem,
	RubricVerdict,
} from "./types.js";

export const RUBRIC_VERDICTS: readonly RubricVerdict[] = [
	"Defective",
	"Arguable",
	"Not defective",
	"Unresolved",
];
export const ENVIRONMENT_VERDICTS: readonly EnvironmentVerdict[] = [
	"Defective",
	"Arguable",
	"Correct",
];
export const AI_REASONING: readonly AiReasoning[] = [
	"Correct",
	"Partly correct",
	"Wrong",
];

function oneOf<T extends string>(
	allowed: readonly T[],
	value: string,
	what: string,
	item: number,
): T {
	const found = allowed.find((candidate) => candidate === value);
	if (found === undefined)
		throw new Error(
			`Worksheet item ${item}: ${what} "${value}" is not one of ${allowed.join(", ")}.`,
		);
	return found;
}

function field(block: string, label: string): string | undefined {
	return new RegExp(`^- \\*\\*${label}:\\*\\* ?(.*)$`, "m").exec(block)?.[1];
}

/** Split a worksheet into one parsed item per `## N. Title — C-NNN` section. */
export function parseWorksheet(text: string): ReviewItem[] {
	const blocks = text
		.split(/^(?=## \d+\. )/m)
		.filter((block) => /^## \d+\. /.test(block));
	return blocks.map((block) => {
		const heading = /^## (\d+)\. (.*)$/m.exec(block);
		const number = Number(heading?.[1]);
		const criterion = heading?.[2]?.split("— ").pop()?.trim() ?? "";
		const task = /\]\(\.\.\/tasks\/([^/]+)\/README\.md\)/.exec(block)?.[1];
		if (!task || !/^C-\d{3}$/.test(criterion))
			throw new Error(`Worksheet item ${number}: task or criterion not found.`);

		const verdict = oneOf(
			RUBRIC_VERDICTS,
			(field(block, "Verdict") ?? "").trim(),
			"verdict",
			number,
		);
		const aiReasoning = oneOf(
			AI_REASONING,
			(field(block, "AI reasoning") ?? "").trim(),
			"AI reasoning",
			number,
		);
		const environmentLine = (field(block, "Environment") ?? "").trim();
		const environment = oneOf(
			ENVIRONMENT_VERDICTS,
			environmentLine.split(":")[0]?.trim() ?? "",
			"environment verdict",
			number,
		);
		const environmentNote = environmentLine.includes(":")
			? environmentLine.slice(environmentLine.indexOf(":") + 1).trim()
			: "";

		// The note starts on its own line and continues through "- " lines until
		// the Category line (or the end of the item).
		const afterNote = block.split(/^- \*\*Note and source locator:\*\* ?/m)[1];
		const noteLines = (afterNote ?? "").split("\n");
		const categoryIndex = noteLines.findIndex((line) =>
			line.startsWith("- **Category**:"),
		);
		const noteBody =
			categoryIndex === -1 ? noteLines : noteLines.slice(0, categoryIndex);
		const note = noteBody
			.map((line) => line.replace(/^- /, "").trim())
			.filter((line) => line.length > 0);
		const category =
			categoryIndex === -1
				? ""
				: (noteLines[categoryIndex] ?? "")
						.replace(/^- \*\*Category\*\*:\s*/, "")
						.trim();
		if (note.length === 0)
			throw new Error(`Worksheet item ${number}: the note is empty.`);

		return {
			number,
			task,
			criterion,
			verdict,
			aiReasoning,
			environment,
			environmentNote,
			note,
			category,
		};
	});
}
