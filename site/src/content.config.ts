import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { z } from "astro/zod";

const findings = defineCollection({
	loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/findings" }),
	schema: z.object({
		title: z.string(),
		summary: z.string(),
		date: z.coerce.date(),
		kind: z.enum(["report", "note", "critique"]),
		author: z.string().default("John J. Hughes, III"),
		/** Drafts render in `astro dev` and previews only, never in production builds. */
		draft: z.boolean().default(false),
		models: z.array(z.string()).default([]),
	}),
});

/** Public methods documentation, rendered from the repository rather than forked. */
const docs = defineCollection({
	loader: glob({ pattern: "METHODS.md", base: "../docs" }),
});

export const collections = { findings, docs };
