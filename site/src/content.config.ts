import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";

/**
 * Markdown renderings of the model runs' deliverables for the LAB explorer.
 * The id is `<task>/<run>/<original file name>`, e.g.
 * `analyze-counterparty-motion-to-dismiss/opus55-low/memo.docx`.
 */
const labDeliverables = defineCollection({
	loader: glob({
		pattern: "*/*/output/*.md",
		base: "../docs/harvey-lab-audit/litigation-dispute-resolution/model-runs",
		generateId: ({ entry }) =>
			entry.replace("/output/", "/").replace(/\.(docx|xlsx)\.md$/, ".$1"),
	}),
});

export const collections = { labDeliverables };
