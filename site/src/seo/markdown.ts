/**
 * Turn MDX source into markdown an agent can quote.
 * JSX components are dropped, their text children kept. Fenced code and
 * inline code spans are left alone, including a shorter fence inside a
 * longer one and the CommonMark equal-delimiter rule for inline spans.
 */

function fenceMarker(line: string): string | null {
	const match = /^( {0,3})(`{3,}|~{3,})/.exec(line);
	return match?.[2] ?? null;
}

function closesFence(line: string, marker: string): boolean {
	const char = marker[0] ?? "`";
	return new RegExp(`^ {0,3}${char}{${marker.length},}\\s*$`).test(line);
}

/** Strip JSX tags outside inline code spans. */
export function stripJsxOutsideCode(line: string): string {
	let out = "";
	let i = 0;
	while (i < line.length) {
		if (line[i] === "`") {
			let length = 0;
			while (line[i + length] === "`") length += 1;
			const closer = line.indexOf("`".repeat(length), i + length);
			if (closer === -1) {
				out += line.slice(i);
				break;
			}
			out += line.slice(i, closer + length);
			i = closer + length;
			continue;
		}
		if (line[i] === "<") {
			const end = line.indexOf(">", i + 1);
			if (
				end !== -1 &&
				/^<\/?[A-Za-z][^>\n]*>?$/.test(line.slice(i, end + 1))
			) {
				i = end + 1;
				continue;
			}
		}
		out += line[i];
		i += 1;
	}
	return out;
}

export function mdxToMarkdown(source: string): string {
	const body = source.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "");
	const lines = body.split("\n");
	const out: string[] = [];
	let fence: string | null = null;
	for (const line of lines) {
		if (fence === null) {
			const marker = fenceMarker(line);
			if (marker) {
				fence = marker;
				out.push(line);
				continue;
			}
			if (/^\s*(import|export)\s/.test(line)) continue;
			out.push(stripJsxOutsideCode(line));
			continue;
		}
		out.push(line);
		if (closesFence(line, fence)) fence = null;
	}
	return `${out
		.join("\n")
		.replace(/\n{3,}/g, "\n\n")
		.trim()}\n`;
}
