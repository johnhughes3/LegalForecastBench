import type { AgentDocument } from "./agent-document.js";
import { absoluteUrl } from "./identity.js";

export function llmsTxt(docs: readonly AgentDocument[]): string {
	const lines = [
		"# LegalForecastBench",
		"",
		"> An open benchmark measuring whether frontier AI models can forecast how federal judges rule on motions to dismiss.",
		"",
		"## For AI agents",
		"",
		"Send `Accept: text/markdown` or `Accept: text/plain` against any page URL on this site to receive markdown at that same address. Do not request a separate `.md` URL.",
		"",
		`Index of the full text: ${absoluteUrl("/llms-full.txt")}`,
		`Sitemap: ${absoluteUrl("/sitemap-index.xml")}`,
		"",
		"## Pages",
		"",
	];
	for (const doc of docs) {
		lines.push(`- [${doc.title}](${absoluteUrl(doc.path)})`);
	}
	lines.push("");
	return lines.join("\n");
}

export function llmsFullTxt(docs: readonly AgentDocument[]): string {
	return `${docs.map((doc) => doc.markdown.trim()).join("\n\n---\n\n")}\n`;
}
